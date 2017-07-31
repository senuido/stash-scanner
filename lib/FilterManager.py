import copy
import itertools
import json
import logging
import os
import pycurl
import re
import threading
from datetime import datetime, timedelta
import time

import jsonschema

from lib.CurrencyManager import cm
from lib.ItemFilter import _ITEM_TYPE, Filter, FilterEncoder
from lib.CompiledFilter import CompiledFilter
from lib.ModFilter import ModFilter, ModFilterType
from lib.ModFilterGroup import AllFilterGroup
from lib.Utility import config, AppException, getJsonFromURL, str2bool, logexception, msgr, get_verror_msg, \
    utc_to_local, CompileException

FILTER_FILE_MISSING = "Missing file: {}"
FILTER_INVALID_JSON = "Error decoding JSON: {} in file {}"
FILTERS_FILE_VALIDATION_ERROR = "Error validating filters file: {}"
FILTERS_FILE_SCHEMA_ERROR = "Filters file schema is invalid: {}"

FM_INVALID_PRICE_THRESHOLD = "Invalid price threshold {}"

_AUTO_FILTERS_FNAME = "tmp\\filters.auto.json"
_USER_FILTERS_FNAME = "cfg\\filters.json"
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
    # "http://poeninja.azureedge.net/api/Data/GetFragmentOverview?league={}",
    # "http://poeninja.azureedge.net/api/Data/GetMapOverview?league={}"
]

_VARIANTS = {
    "Physical":			"([0-9]+)% increased Physical Damage$",
    "Cold":				"([0-9]+)% increased Cold Damage$",
    "Fire":				"([0-9]+)% increased Fire Damage$",
    "Lightning":		"([0-9]+)% increased Lightning Damage$",
    "ES":				"([0-9]+)% increased Energy Shield$",
    "Armour":			"([0-9]+)% increased Armour$",
    "Armour/Evasion/ES":"([0-9]+)% increased Armour, Evasion and Energy Shield$",
    "Armour/ES":		"([0-9]+)% increased Armour and Energy Shield$",
    "Evasion/ES":		"([0-9]+)% increased Evasion and Energy Shield$",
    "Evasion/ES/Life":	"([0-9]+)% increased Evasion and Energy Shield$",
    "Evasion":			"([0-9]+)% increased Evasion Rating$",
    "Armour/Evasion":	"([0-9]+)% increased Armour and Evasion$",
    "Armour/ES/Life":	"([0-9]+)% increased Armour and Evasion$",
    "Added Attacks":	"Adds ([0-9]+) to ([0-9]+) Lightning Damage to Attacks during Flask effect$",
    "Added Spells":		"Adds ([0-9]+) to ([0-9]+) Lightning Damage to Spells during Flask effect$",
    "Penetration":		"Damage Penetrates 10% Lightning Resistance during Flask effect$",
    "Conversion": 		"20% of Physical Damage Converted to Lightning during Flask effect$"
}


class FilterManager:
    filter_file_lock = {_USER_FILTERS_FNAME: threading.Lock(),
                        _AUTO_FILTERS_FNAME: threading.Lock()}
    config_file_lock = threading.Lock()
    UPDATE_INTERVAL = 10  # minutes

    def __init__(self):
        self.init()

    def init(self):
        self.userFilters = []
        self.autoFilters = []
        self.compiledFilters = []
        self.activeFilters = []

        self.disabled_categories = []
        self.price_threshold = '1 exalted'
        self.default_price_override = "* 1"
        self.default_fprice_override = "* 0.8"
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
            self.price_threshold = data.get('price_threshold', '1 exalted')
            self.default_price_override = data.get('default_price_override', '* 1')
            self.default_fprice_override = data.get('default_fprice_override', '* 0.8')
            self.price_overrides = data.get('price_overrides', {})
            self.filter_price_overrides = data.get('filter_price_overrides', {})
            self.filter_state_overrides = data.get('filter_state_overrides', {})

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
            'default_price_override': self.default_price_override,
            'default_fprice_override': self.default_fprice_override,
            'price_threshold': self.price_threshold,
            'price_overrides': self.price_overrides,
            'filter_price_overrides': self.filter_price_overrides,
            'filter_state_overrides': self.filter_state_overrides
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

    def fetchFromAPI(self, force_update=False):
        if not force_update and not self.needUpdate:
            return

        # print('updating filters..')

        try:
            filter_ids = []
            filters = []
            c = pycurl.Curl()
            for url in _URLS:
                furl = url.format(config.league)
                data = getJsonFromURL(furl, handle=c, max_attempts=3)
                if data is None:
                    raise AppException("Filters update failed. Bad response from server")

                category = re.match(".*Get(.*)Overview", furl).group(1).lower()

                for item in data['lines']:
                    crit = {}
                    crit['price_max'] = "{} exalted".format(float(item.get('exaltedValue', 0)))
                    crit['name'] = [item['name'].lower()]
                    crit['type'] = [_ITEM_TYPE[item['itemClass']]]
                    crit['buyout'] = True

                    title = "{} {} {}".format(
                        'Legacy' if 'relic' in crit['type'] else '',
                        item['name'],
                        item['variant'] if item['variant'] is not None else '').strip()

                    # find a unique id
                    base_id = '_' + title.lower().replace(' ', '_')
                    id = base_id
                    n = 2
                    while id in filter_ids:
                        id = '{}{}'.format(base_id, n)
                        n += 1

                    filter_ids.append(id)
                    # if n > 2:
                    #     print('base_id {} was taken, using {} instead'.format(base_id, id))

                    fltr = Filter(title, crit, False, category, id=id)

                    if item['variant'] is not None:
                        if item['variant'] not in _VARIANTS:
                            msgr.send_msg("Unknown variant {} in item {}".format(item['variant'], item['name']),
                                          logging.WARN)
                        else:
                            # crit['explicit'] = {'mods': [{'expr': _VARIANTS[item['variant']]}]}
                            fg = AllFilterGroup()
                            fg.mfs = [ModFilter(ModFilterType.Explicit, _VARIANTS[item['variant']])]
                            fltr.criteria['fgs'] = [fg.toDict()]

                    fltr.validate()
                    filters.append(fltr)

            self.autoFilters = filters
            self.item_prices = self.getPrices(self.autoFilters)
            self.saveAutoFilters()
            self.last_update = datetime.utcnow()
        except pycurl.error as e:
            raise AppException("Filters update failed. Connection error: {}".format(e))
        except (KeyError, ValueError) as e:
            raise AppException("Filters update failed. Parsing error: {}".format(e))
        except Exception as e:
            logexception()
            raise AppException("Filters update failed. Unexpected error: {}".format(e))

    def loadUserFilters(self, validate=True):
        try:
            self.userFilters, last_update = FilterManager.loadFiltersFromFile(_USER_FILTERS_FNAME, validate)
        except FileNotFoundError:
            self.userFilters = []
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

    def updateConfig(self, default_price_override, default_fprice_override, price_threshold,
                     price_overrides, filter_price_overrides, filter_state_overrides):
        with self.compile_lock:
            backup = copy.copy(self)

            self.default_price_override = default_price_override
            self.default_fprice_override = default_fprice_override
            self.price_threshold = price_threshold
            self.price_overrides = price_overrides
            self.filter_price_overrides = filter_price_overrides
            self.filter_state_overrides = filter_state_overrides

            try:
                self.validateConfig()
                self.saveConfig()
            except Exception:
                self.default_price_override = backup.default_price_override
                self.default_fprice_override = backup.default_fprice_override
                self.price_threshold = price_threshold
                self.price_overrides = backup.price_overrides
                self.filter_price_overrides = backup.filter_price_overrides
                self.filter_state_overrides = backup.filter_state_overrides

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
                              logging.WARN)

        active_filters = [fltr for fltr in filters if fltr.enabled]

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

        for override in set(self.price_overrides) - used_price_overrides:
            msgr.send_msg('Unused item price override: {}'.format(override), logging.WARN)

    def applyOverrides(self, filters):
        used_price_overrides = set()
        used_state_overrides = set()

        tamount, tshort = cm.priceFromString(self.price_threshold)
        min_val = cm.convert(float(tamount), tshort)

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

        for override in set(self.filter_price_overrides) - used_price_overrides:
            msgr.send_msg('Unused filter price override: {}'.format(override), logging.WARN)

        for override in set(self.filter_state_overrides) - used_state_overrides:
            msgr.send_msg('Unused filter state override: {}'.format(override), logging.WARN)

    def validateConfig(self):
        if not cm.isPriceValid(self.price_threshold):
            raise AppException(FM_INVALID_PRICE_THRESHOLD.format(self.price_threshold))

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
                if validate_data:
                    fltr.validate()
                filters.append(fltr)

            last_update = data.get('last_update', '')
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



def lower_json(x):
    if isinstance(x, list):
        return [lower_json(v) for v in x]
    if isinstance(x, dict):
        d = {}
        for k, v in x.items():
            if k.lower() in ('title', 'expr', 'name', 'description'):
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