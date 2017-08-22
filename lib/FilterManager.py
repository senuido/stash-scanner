import copy
import itertools
import json
import logging
import os
import pycurl
import re
import threading
import time
from datetime import datetime, timedelta
from enum import IntEnum

import jsonschema

from lib.CompiledFilter import CompiledFilter
from lib.CurrencyManager import cm
from lib.ItemClass import ItemClass
from lib.ItemFilter import _ITEM_TYPE, Filter, FilterEncoder, _NAME_TO_TYPE, FilterPriority
from lib.ItemHelper import ItemRarity, ItemType
from lib.ModFilter import ModFilter, ModFilterType
from lib.ModFilterGroup import AllFilterGroup
from lib.Utility import config, AppException, getJsonFromURL, str2bool, logexception, msgr, get_verror_msg, \
    utc_to_local, CompileException, ConfidenceLevel

FILTER_FILE_MISSING = "Missing file: {}"
FILTER_INVALID_JSON = "Error decoding JSON: {} in file {}"
FILTERS_FILE_VALIDATION_ERROR = "Error validating filters file: {}"
FILTERS_FILE_SCHEMA_ERROR = "Filters file schema is invalid: {}"

_AUTO_FILTERS_FNAME = "tmp\\filters.auto.json"
_USER_FILTERS_FNAME = "cfg\\filters.json"
_USER_DEFAULT_FILTERS_FNAME = "cfg\\filters.example.json"
FILTERS_CFG_FNAME = "cfg\\filters.config.json"
FILTERS_FILE_SCHEMA_FNAME = "res\\filters_file.schema.json"

_URLS = [
    "http://poeninja.azureedge.net/api/Data/GetDivinationCardsOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetEssenceOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueJewelOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueMapOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueFlaskOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueWeaponOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueArmourOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueAccessoryOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetProphecyOverview?league={}",
    # "http://poeninja.azureedge.net/api/Data/GetMapOverview?league={}"
]

_VARIANTS = {
    # Doryani's Invitation
    "Physical":			("([0-9]+)% increased Physical Damage$", ),
    "Cold":				("([0-9]+)% increased Cold Damage$", ),
    "Fire":				("([0-9]+)% increased Fire Damage$", ),
    "Lightning":		("([0-9]+)% increased Lightning Damage$", ),

    # Atziri's Splendour
    "Armour": ("([0-9]+)% increased Armour$", "\\+([0-9]+) to maximum Life$"),
    "Evasion": ("([0-9]+)% increased Evasion Rating$", "\\+([0-9]+) to maximum Life$"),
    "ES": ("([0-9]+)% increased Energy Shield$", "\\+([0-9]+) to maximum Energy Shield$"),

    "Armour/ES": ("([0-9]+)% increased Armour and Energy Shield$", "\\+([0-9]+) to maximum Energy Shield$"),
    "Evasion/ES": ("([0-9]+)% increased Evasion and Energy Shield$", "\\+([0-9]+) to maximum Energy Shield$"),

    "Armour/Evasion": ("([0-9]+)% increased Armour and Evasion$", "\\+([0-9]+) to maximum Life$"),
    "Evasion/ES/Life": ("([0-9]+)% increased Evasion and Energy Shield$", "\\+([0-9]+) to maximum Life$"),
    "Armour/ES/Life": ("([0-9]+)% increased Armour and Energy Shield$", "\\+([0-9]+) to maximum Life$"),

    "Armour/Evasion/ES": ("([0-9]+)% increased Armour, Evasion and Energy Shield$", ),

    # Vessel of Vinktar
    "Added Attacks":	("Adds ([0-9]+) to ([0-9]+) Lightning Damage to Attacks during Flask effect$", ),
    "Added Spells":		("Adds ([0-9]+) to ([0-9]+) Lightning Damage to Spells during Flask effect$", ),
    "Penetration":		("Damage Penetrates ([0-9]+)% Lightning Resistance during Flask effect$", ),
    "Conversion": 		("([0-9]+)% of Physical Damage Converted to Lightning during Flask effect$", ),
}

class FilterVersion(IntEnum):
    V1 = 1
    V2 = 2
    Latest = V2

class FilterManager:
    filter_file_lock = {_USER_DEFAULT_FILTERS_FNAME: threading.Lock(),
                        _USER_FILTERS_FNAME: threading.Lock(),
                        _AUTO_FILTERS_FNAME: threading.Lock()}
    config_file_lock = threading.Lock()
    UPDATE_INTERVAL = 10  # minutes

    DEFAULT_BUDGET = '200 chaos'
    DEFAULT_MIN_PRICE = ''
    DEFAULT_PRICE_THRESHOLD = '10 chaos'
    DEFAULT_PRICE_OVERRIDE = '* 1'
    DEFAULT_FPRICE_OVERRIDE = '-15 chaos'
    DEFAULT_CONFIDENCE_LEVEL = ConfidenceLevel.Medium.value
    DEFAULT_ENABLE_5L_FILTERS = True

    def __init__(self):
        self.init()

    def init(self):
        self.userFilters = []
        self.autoFilters = []
        self.compiledFilters = []
        self.activeFilters = []

        self.disabled_categories = []
        self.price_threshold = self.DEFAULT_PRICE_THRESHOLD
        self.budget = self.DEFAULT_BUDGET
        self.default_min_price = self.DEFAULT_MIN_PRICE
        self.default_price_override = self.DEFAULT_PRICE_OVERRIDE
        self.default_fprice_override = self.DEFAULT_FPRICE_OVERRIDE
        self.confidence_level = self.DEFAULT_CONFIDENCE_LEVEL
        self.enable_5l_filters = self.DEFAULT_ENABLE_5L_FILTERS
        self.price_overrides = {}
        self.filter_price_overrides = {}
        self.filter_state_overrides = {}
        self.last_update = None  # last update of auto filters
        self.validation_required = True

        # compiled prices cache for UI queries
        self.item_prices = {}
        self.compiled_item_prices = {}
        self.compiled_filter_prices = {}

        self.initialized = False
        self.compile_lock = threading.Lock()

    def loadConfig(self):
        try:
            try:
                with self.config_file_lock:
                    with open(FILTERS_CFG_FNAME, encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
            except FileNotFoundError:
                data = {}
            self.disabled_categories = data.get('disabled_categories', [])
            self.price_threshold = data.get('price_threshold', self.DEFAULT_PRICE_THRESHOLD)
            self.budget = data.get('budget', self.DEFAULT_BUDGET)
            self.default_min_price = data.get('default_min_price', self.DEFAULT_MIN_PRICE)
            self.default_price_override = data.get('default_price_override', self.DEFAULT_PRICE_OVERRIDE)
            self.default_fprice_override = data.get('default_fprice_override', self.DEFAULT_FPRICE_OVERRIDE)
            self.price_overrides = data.get('price_overrides', {})
            self.filter_price_overrides = data.get('filter_price_overrides', {})
            self.filter_state_overrides = data.get('filter_state_overrides', {})
            self.confidence_level = data.get('confidence_level', self.DEFAULT_CONFIDENCE_LEVEL)
            self.enable_5l_filters = data.get('enable_5l_filters', self.DEFAULT_ENABLE_5L_FILTERS)

            try:
                self.validateConfig()
            except AppException as e:
                raise AppException('Failed validating filters configuration. {}'.format(e))

            self.saveConfig()
        except Exception as e:
            logexception()
            raise AppException('Failed loading filters configuration. Unexpected error: {}'.format(e))


    def saveConfig(self):
        data = {
            'disabled_categories': self.disabled_categories,
            'price_threshold': self.price_threshold,
            'budget': self.budget,
            'default_min_price': self.default_min_price,
            'default_price_override': self.default_price_override,
            'default_fprice_override': self.default_fprice_override,
            'price_overrides': self.price_overrides,
            'filter_price_overrides': self.filter_price_overrides,
            'filter_state_overrides': self.filter_state_overrides,
            'confidence_level': self.confidence_level,
            'enable_5l_filters': self.enable_5l_filters
        }
        with self.config_file_lock:
            with open(FILTERS_CFG_FNAME, mode="w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=4, separators=(',', ': '), sort_keys=True)

    @property
    def needUpdate(self):
        return not self.last_update or (datetime.utcnow() - self.last_update) >= timedelta(minutes=FilterManager.UPDATE_INTERVAL)

    @property
    def filter_prices(self):
        return self.compiled_item_prices

    def fetchFromAPI(self, force_update=False, accept_empty=False):
        if not force_update and not self.needUpdate:
            return

        # print('updating filters..')

        try:
            filter_ids = []
            filters = []

            def name_to_id(name):
                return '_' + name.lower().replace(' ', '_')

            def get_unique_id(title, name, category, links):
                title_id = name_to_id(title)
                if title_id not in filter_ids:
                    return title_id

                name_id = name_to_id('{}{}'.format(name, ' {}L'.format(links) if links else ''))
                if name_id not in filter_ids:
                    # print('id {} was taken, using name id {} instead'.format(title_id, name_id))
                    return name_id

                category_id = name_to_id(title + ' ' + category)
                if category_id not in filter_ids:
                    # print('id {} was taken, using category id {} instead'.format(title_id, category_id))
                    return category_id

                id = title_id
                n = 2
                while id in filter_ids:
                    id = '{}{}'.format(title_id, n)
                    n += 1
                # if n > 2:
                #     print('id {} was taken, using {} instead'.format(title_id, id))

                return id

            c = pycurl.Curl()
            for url in _URLS:
                furl = url.format(config.league)
                data = getJsonFromURL(furl, handle=c, max_attempts=3)
                if data is None and not accept_empty:
                    raise AppException("Filters update failed. Empty response from server")

                if data:
                    category = re.match(".*Get(.*)Overview", furl).group(1).lower()

                    for item in data['lines']:
                        if item['count'] < self.confidence_level:
                            continue
                        priority = FilterPriority.AutoBase
                        crit = {}
                        # crit['price_max'] = "{} exalted".format(float(item.get('exaltedValue', 0)))
                        crit['price_max'] = "{} chaos".format(float(item.get('chaosValue', 0)))
                        base = item['baseType'] if category not in ('essence', ) else None
                        name = item['name']
                        if base:
                            name += ' ' + base
                        crit['name'] = ['"{}"'.format(name)]

                        try:
                            rarity = ItemRarity(item['itemClass'])
                            crit['rarity'] = [_ITEM_TYPE[rarity]]
                        except ValueError:
                            rarity = None

                        crit['buyout'] = True
                        links = item['links']
                        title = "{} {} {}".format(
                            'Legacy' if rarity == ItemRarity.Relic else '',
                            item['name'],
                            item['variant'] if item['variant'] is not None else '').strip()

                        if links:
                            title = '{} {}L'.format(title, links)
                            crit['links_min'] = links
                            if links == 5:
                                priority += 1
                            elif links == 6:
                                priority += 2

                        id = get_unique_id(title, name, category, links)
                        filter_ids.append(id)

                        fltr = Filter(title, crit, False, category, id=id, priority=priority)

                        if item['variant'] is not None:
                            if item['variant'] not in _VARIANTS:
                                msgr.send_msg("Unknown variant {} in item {}".format(item['variant'], item['name']),
                                              logging.WARN)
                            else:
                                # crit['explicit'] = {'mods': [{'expr': _VARIANTS[item['variant']]}]}
                                fg = AllFilterGroup()
                                for expr in _VARIANTS[item['variant']]:
                                    fg.addModFilter(ModFilter(ModFilterType.Explicit, expr))

                                fltr.criteria['fgs'] = [fg.toDict()]

                        fltr.validate()
                        filters.append(fltr)

            self.autoFilters = filters
            self.item_prices = self.getPrices(self.autoFilters)
            self.saveAutoFilters()
            self.last_update = datetime.utcnow() if filters else None
        except pycurl.error as e:
            raise AppException("Filters update failed. Connection error: {}".format(e))
        except (KeyError, ValueError) as e:
            raise AppException("Filters update failed. Parsing error: {}".format(e))
        except AppException:
            raise
        except Exception as e:
            logexception()
            raise AppException("Filters update failed. Unexpected error: {}".format(e))

    def _loadDefaultFilters(self, validate=True):
        try:
            self.userFilters, last_update = FilterManager.loadFiltersFromFile(_USER_DEFAULT_FILTERS_FNAME, validate)
        except Exception:
            self.userFilters = []

    def loadUserFilters(self, validate=True):
        try:
            self.userFilters, last_update = FilterManager.loadFiltersFromFile(_USER_FILTERS_FNAME, validate)
        except FileNotFoundError:
            self._loadDefaultFilters()
            self.saveUserFilters()
        except AppException:
            raise
        except Exception as e:
            logexception()
            raise AppException("Loading user filters failed. Unexpected error: {}".format(e))

    def loadAutoFilters(self, validate=True):
        try:
            self.autoFilters, self.last_update = FilterManager.loadFiltersFromFile(_AUTO_FILTERS_FNAME, validate)
            self.item_prices = self.getPrices(self.autoFilters)
        except FileNotFoundError as e:
            raise AppException("Loading generated filters failed. Missing file {}", e.filename)
        except AppException:
            raise
        except Exception as e:
            logexception()
            raise AppException("Loading generated filters failed. Unexpected error: {}".format(e))

    def saveUserFilters(self):
        FilterManager.saveFiltersToFile(_USER_FILTERS_FNAME, self.userFilters)

    def saveAutoFilters(self):
        FilterManager.saveFiltersToFile(_AUTO_FILTERS_FNAME, self.autoFilters)

    def validateFilters(self):
        valid = True

        verrors = {}
        for fltr in self.getRawFilters():
            try:
                fltr.validate()
            except AppException as e:
                verrors[fltr] = e
                valid = False

        for fltr, e in verrors.items():
            msgr.send_msg('{}: {}'.format(fltr.title or fltr.id, e), logging.ERROR)

        for fltr in self.userFilters:
            if fltr.id.startswith('_'):
                msgr.send_msg('{}; Invalid ID {}, underscore prefix is reserved for generated filters'.format(fltr.title, fltr.id), logging.ERROR)
                valid = False

        filters = list(self.getRawFilters())
        for fid in self.getFilterIds():
            matches = self.getFiltersById(fid, filters)
            if len(matches) > 1:
                msgr.send_msg('Duplicate ID {} detected for filters: {}'.format(fid, (fltr.title for fltr in matches)), logging.ERROR)
                valid = False

        if valid:
            self.validation_required = False
            msgr.send_msg('Filters passed validation.', logging.INFO)
        return valid

    def updateConfig(self, default_price_override, default_fprice_override, price_threshold, budget, min_price,
                     price_overrides, filter_price_overrides, filter_state_overrides, confidence_level, enable_5l_filters):
        with self.compile_lock:
            backup = copy.copy(self)

            self.default_price_override = default_price_override
            self.default_fprice_override = default_fprice_override
            self.price_threshold = price_threshold
            self.budget = budget
            self.default_min_price = min_price
            self.price_overrides = price_overrides
            self.filter_price_overrides = filter_price_overrides
            self.filter_state_overrides = filter_state_overrides
            self.confidence_level = confidence_level
            self.enable_5l_filters = enable_5l_filters

            try:
                self.validateConfig()
                self.saveConfig()
            except Exception:
                self.default_price_override = backup.default_price_override
                self.default_fprice_override = backup.default_fprice_override
                self.price_threshold = price_threshold
                self.budget = backup.budget
                self.default_min_price = backup.default_min_price
                self.price_overrides = backup.price_overrides
                self.filter_price_overrides = backup.filter_price_overrides
                self.filter_state_overrides = backup.filter_state_overrides
                self.confidence_level = backup.confidence_level
                self.enable_5l_filters = backup.enable_5l_filters

                # self.loadConfig()
                raise

    def compileFilters(self, force_validation=False):
        with self.compile_lock:
            try:
                if self.validation_required or force_validation:
                    start = time.time()
                    valid = self.validateFilters()
                    end = time.time() - start
                    msgr.send_msg('Filters validation time {:.4f}s'.format(end), logging.DEBUG)
                    if not valid:
                        raise AppException('Filter validation failed.')

                self._compileFilters()
                msg = 'Filters compiled successfully.'
                if len(self.getActiveFilters()):
                    msg += ' {} are active.'.format(len(self.getActiveFilters()))
                msgr.send_msg(msg, logging.INFO)
            except Exception as e:
                # configuration is valid yet compile failed, stop
                self.compiledFilters = []
                self.activeFilters = []
                self.compiled_item_prices = {}
                self.compiled_filter_prices = {}
                if isinstance(e, AppException):
                    msgr.send_msg(e, logging.ERROR)
                else:
                    logexception()
                    msgr.send_msg('Unexpected error while compiling filters: {}'.format(e), logging.ERROR)
            finally:
                msgr.send_object(FiltersInfo())

    def _compileFilters(self):
        filters = []

        for fltr in self.autoFilters:
            try:
                comp = self.compileFilter(fltr)
                cf = CompiledFilter(fltr, comp)
                cf.enabled = fltr.category not in self.disabled_categories
                if not self.enable_5l_filters:
                    cf.enabled = '_5l' not in cf.fltr.id
                filters.append(cf)
            except CompileException as e:
                msgr.send_msg('Failed compiling filter {}: {}'.format(fltr.title, e), logging.WARN)

        item_prices = self.getPrices(self.autoFilters)

        self.applyItemPriceOverrides(filters)

        compiled_item_prices = self.getCompiledPrices(filters)

        user_filters = []

        for fltr in self.userFilters:
            try:
                comp = self.compileFilter(fltr)
                cf = CompiledFilter(fltr, comp)
                cf.enabled = fltr.enabled and fltr.category not in self.disabled_categories and fltr.criteria
                user_filters.append(cf)
            except CompileException as e:
                msgr.send_msg('Failed compiling filter {}: {}'.format(fltr.title, e), logging.WARN)

        # apply filter overrides only after user filters are compiled
        self.applyOverrides(filters)

        compiled_filter_prices = self.getCompiledPrices(filters)

        filters = user_filters + filters

        for cf in filters:
            if cf.enabled and 'price_max' in cf.comp and cf.comp['price_max'] <= 0:
                cf.enabled = False
                msgr.send_msg('Filter disabled: {}. price max must be higher than zero.'.format(cf.getDisplayTitle()),
                              logging.DEBUG)

        active_filters = [cf for cf in filters if cf.enabled]
        active_filters.sort(key=lambda cf: cf.fltr.priority, reverse=True)

        for cf in filters:
            cf.finalize()

        self.activeFilters = active_filters
        self.compiledFilters = filters

        self.item_prices = item_prices
        self.compiled_item_prices = compiled_item_prices
        self.compiled_filter_prices = compiled_filter_prices

    def applyItemPriceOverrides(self, filters):
        used_price_overrides = set()

        for cf in filters:
            override = self.default_price_override
            for id in self.price_overrides:
                if id.lower() == cf.fltr.id:
                    override = self.price_overrides[id]
                    used_price_overrides.add(id)
                    break

            cf.comp['price_max'] = cm.compilePrice(override, cf.comp['price_max'])

        # for override in set(self.price_overrides) - used_price_overrides:
        #     msgr.send_msg('Unused item price override: {}'.format(override), logging.WARN)

    def applyOverrides(self, filters):
        used_price_overrides = set()
        used_state_overrides = set()

        tamount, tshort = cm.priceFromString(self.price_threshold)
        min_val = cm.convert(float(tamount), tshort)

        min_price = cm.compilePrice(fm.default_min_price) if self.default_min_price else None

        for cf in filters:
            # title = re.match('(.+) \(.+\)', fltr.title.lower()).group(1)

            override = self.default_fprice_override
            for id in self.filter_price_overrides:
                if id.lower() == cf.fltr.id:
                    override = self.filter_price_overrides[id]
                    used_price_overrides.add(id)
                    break

            state = cf.enabled and cf.comp.get('price_max', 0) >= min_val
            for id in self.filter_state_overrides:
                if id.lower() == cf.fltr.id:
                    state = self.filter_state_overrides[id]
                    used_state_overrides.add(id)

            cf.enabled = state
            cf.comp['price_max'] = cm.compilePrice(override, cf.comp['price_max'])

            if min_price is not None:
                cf.comp['price_min'] = cm.compilePrice(fm.default_min_price)

        # for override in set(self.filter_price_overrides) - used_price_overrides:
        #     msgr.send_msg('Unused filter price override: {}'.format(override), logging.WARN)
        #
        # for override in set(self.filter_state_overrides) - used_state_overrides:
        #     msgr.send_msg('Unused filter state override: {}'.format(override), logging.WARN)

    def validateConfig(self):
        if not cm.isPriceValid(self.price_threshold):
            raise AppException("Invalid price threshold {}".format(self.price_threshold))

        if self.budget and not cm.isPriceValid(self.budget):
            raise AppException("Invalid budget price {}".format(self.budget))

        if self.default_min_price and not cm.isPriceValid(self.default_min_price):
            raise AppException("Invalid minimum price {}".format(self.default_min_price))

        self.validateOverrides()

    def validateOverrides(self):
        for key, state in self.filter_state_overrides.items():
            if not isinstance(state, bool):
                try:
                    self.filter_state_overrides[key] = str2bool(str(state))
                except ValueError:
                    raise AppException("Invalid state override '{}' for {}. Must be a boolean.".format(state, key))

        if not cm.isOverridePriceValid(self.default_price_override):
            raise AppException("Invalid default price override {}".format(self.default_price_override))

        for key, override in self.price_overrides.items():
            if not cm.isOverridePriceValid(override):
                raise AppException("Invalid price override '{}' for {}".format(override, key))

        if not cm.isOverridePriceValid(self.default_fprice_override):
            raise AppException("Invalid default filter price override {}".format(self.default_fprice_override))

        for key, override in self.filter_price_overrides.items():
            if not cm.isOverridePriceValid(override):
                raise AppException("Invalid filter price override '{}' for {}".format(override, key))

    def getRawFilters(self):
        return itertools.chain(self.userFilters, self.autoFilters)

    def getFilterIds(self):
        return {fltr.id for fltr in self.getRawFilters() if fltr.id}

    def getFilters(self):
        return self.compiledFilters

    def getActiveFilters(self):
        return self.activeFilters

    def compileFilter(self, fltr, path=None):
        if path is None:
            path = []
        if fltr.id in path:
            raise AppException("Circular reference detected while compiling filters: {}".format(path))
        path.append(fltr.id)

        if not fltr.baseId or fltr.baseId == fltr.id:
            baseComp = {}
        else:
            baseFilter = self.getFilterById(fltr.baseId, itertools.chain(self.userFilters, self.autoFilters))
            if baseFilter is None:
                # try using last compilation
                compiledFilter = self.getFilterById(fltr.baseId, self.activeFilters, lambda x, y: x.fltr.id == y)
                if compiledFilter is None:
                    raise CompileException("Base filter '{}' not found.".format(fltr.baseId))
                    # return None
                baseComp = self.compileFilter(compiledFilter.fltr, path)
            else:
                baseComp = self.compileFilter(baseFilter, path)

        # if baseComp is None:
        #     return None

        return fltr.compile(baseComp)

    def getCategories(self):
        return {fltr.category for fltr in self.getRawFilters() if fltr.category}

    @staticmethod
    def getPrices(filters):
        prices = {}
        for fltr in filters:
            if fltr.id:
                prices[fltr.id] = fltr.criteria['price_max']
        return prices

    @staticmethod
    def getCompiledPrices(filters):
        prices = {}
        for cf in filters:
            if cf.fltr.id:
                prices[cf.fltr.id] = cf.comp['price_max']
        return prices


    @staticmethod
    def getFilterById(id, filters, match=lambda x, y: x.id == y):
        if id == '' or id is None:
            return None

        for fltr in filters:
            if match(fltr, id):
                return fltr
        return None

    @staticmethod
    def getFiltersById(id, filters, match=lambda x, y: x.id == y):
        matches = []

        if id == '' or id is None:
            return matches

        for fltr in filters:
            if match(fltr, id):
                matches.append(fltr)

        return matches

    @classmethod
    def saveFiltersToFile(cls, fname, filters):
        with cls.filter_file_lock[fname]:
            data = {
                'filters': filters,
                'version': FilterVersion.Latest,
                'last_update': datetime.utcnow()
            }

            with open(fname, mode="w", encoding="utf-8", errors="replace") as f:
                json.dump(data, f, indent=4, separators=(',', ': '), cls=FilterEncoder)

    @classmethod
    def loadFiltersFromFile(cls, fname, validate_data):
        filters = []

        cur_fname = fname
        try:
            with cls.filter_file_lock[fname]:
                with open(cur_fname, encoding="utf-8", errors="replace") as f:
                    data = json.load(f)

            cur_fname = FILTERS_FILE_SCHEMA_FNAME  # TODO: move schema loading to main init and store in class
            with open(cur_fname) as f:
                schema = json.load(f)

            # normalize keys and values
            data = lower_json(data)

            jsonschema.validate(data, schema)

            for item in data.get('filters', []):
                fltr = Filter.fromDict(item)
                filters.append(fltr)

            ver = data.get('version', FilterVersion.V1)
            if ver != FilterVersion.Latest:
                FilterManager.convert(ver, filters)
            last_update = data.get('last_update', '')

            if validate_data:
                for fltr in filters:
                    fltr.validate()

            try:
                last_update = datetime.strptime(last_update, '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                last_update = datetime.utcnow() - timedelta(minutes=FilterManager.UPDATE_INTERVAL)
        except FileNotFoundError:
            if cur_fname != FILTERS_FILE_SCHEMA_FNAME:
                raise
            else:
                raise AppException(FILTER_FILE_MISSING.format(cur_fname))
        except jsonschema.ValidationError as e:
            raise AppException(FILTERS_FILE_VALIDATION_ERROR.format(get_verror_msg(e, data)))
        except jsonschema.SchemaError as e:
            raise AppException(FILTERS_FILE_SCHEMA_ERROR.format(e.message))
        except json.decoder.JSONDecodeError as e:
            raise AppException(FILTER_INVALID_JSON.format(e, cur_fname))

        return filters, last_update

    @classmethod
    def clearCache(cls):
        fname = _AUTO_FILTERS_FNAME
        with cls.filter_file_lock[fname]:
            try:
                os.remove(fname)
            except FileNotFoundError:
                pass

    @staticmethod
    def convert(ver, filters):
        if ver == FilterVersion.V1:
            def is_type_rarity(item_type):
                try:
                    ItemRarity(_NAME_TO_TYPE[item_type])
                    return True
                except ValueError:
                    return False

            def type_to_item_class(item_type):
                val = _NAME_TO_TYPE[item_type]
                if val == ItemType.DivinationCard:
                    return ItemClass.DivinationCard
                if val == ItemType.Prophecy:
                    return ItemClass.Prophecy
                if val == ItemType.Gem:
                    return ItemClass.Gem
                if val == ItemType.Currency:
                    return ItemClass.Currency
                return None

            for fltr in filters:
                types = fltr.criteria.get('type')
                if types:
                    rarity = [item_type for item_type in types if is_type_rarity(item_type)]
                    fltr.criteria['rarity'] = rarity

                    for item_type in types:
                        iclass = type_to_item_class(item_type)
                        if iclass:
                            fltr.criteria['iclass'] = iclass.name
                            break

                    fltr.criteria.pop('type')



def lower_json(x):
    if isinstance(x, list):
        return [lower_json(v) for v in x]
    if isinstance(x, dict):
        d = {}
        for k, v in x.items():
            if k.lower() in ('title', 'expr', 'name', 'description', 'iclass'):
                d[k.lower()] = v
            else:
                d[k.lower()] = lower_json(v)
        return d
        # return {k.lower(): lower_keys(v) for k, v in x.items()}
    if isinstance(x, str):
        return x.lower()
    return x

class FiltersInfo:
    def __init__(self):
        self.user_filters = [cf.getDisplayTitle() for cf in fm.getActiveFilters() if cf.fltr in fm.userFilters]
        self.auto_filters = [cf.getDisplayTitle() for cf in fm.getActiveFilters() if cf.fltr in fm.autoFilters]
        self.n_loaded = len(fm.getFilters())
        self.n_active = len(fm.getActiveFilters())
        self.last_update = utc_to_local(fm.last_update) if fm.last_update else None

fm = FilterManager()