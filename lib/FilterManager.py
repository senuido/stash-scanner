import json

import re

import pycurl
import threading

import itertools

import logging
from jsonschema import validate, ValidationError, SchemaError
from lib.Utility import config, AppException, getJsonFromURL, str2bool, logexception, msgr
from lib.CurrencyManager import cm
from lib.ItemHelper import Filter, _ITEM_TYPE, FilterEncoder, CompiledFilter

FILTER_FILE_MISSING = "Missing file: {}"
FILTER_INVALID_JSON = "Error decoding JSON: {} in file {}"
FILTER_VALIDATION_ERROR = "Error validating filter: {}"
FILTER_SCHEMA_ERROR = "Filter schema error: {}"

FM_INVALID_PRICE_THRESHOLD = "Invalid price threshold {}"

_AUTO_FILTERS_FNAME = "tmp\\filters.auto.json"
_FILTERS_CFG_FNAME = "cfg\\filters.config.json"
_USER_FILTERS_FNAME = "cfg\\filters.json"
_FILTER_SCHEMA_FNAME = "res\\filters.schema.json"

_URLS = [
    "http://poeninja.azureedge.net/api/Data/GetDivinationCardsOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetEssenceOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueJewelOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueMapOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueFlaskOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueWeaponOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueArmourOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueAccessoryOverview?league={}",
    "http://poeninja.azureedge.net/api/Data/GetUniqueMapOverview?league={}"]

_VARIANTS = {
    "Physical":			"[0-9]+% increased Physical Damage$",
    "Cold":				"[0-9]+% increased Cold Damage$",
    "Fire":				"[0-9]+% increased Fire Damage$",
    "Lightning":		"[0-9]+% increased Lightning Damage$",
    "ES":				"[0-9]+% increased Energy Shield$",
    "Armour":			"[0-9]+% increased Armour$",
    "Armour/Evasion/ES":"[0-9]+% increased Armour, Evasion and Energy Shield$",
    "Armour/ES":		"[0-9]+% increased Armour and Energy Shield$",
    "Evasion/ES":		"[0-9]+% increased Evasion and Energy Shield$",
    "Evasion/ES/Life":	"[0-9]+% increased Evasion and Energy Shield$",
    "Evasion":			"[0-9]+% increased Evasion Rating$",
    "Armour/Evasion":	"[0-9]+% increased Armour and Evasion$",
    "Armour/ES/Life":	"[0-9]+% increased Armour and Evasion$",
    "Added Attacks":	"Adds [0-9]+ to [0-9]+ Lightning Damage to Attacks during Flask effect$",
    "Added Spells":		"Adds [0-9]+ to [0-9]+ Lightning Damage to Spells during Flask effect$",
    "Penetration":		"Damage Penetrates 10% Lightning Resistance during Flask effect",
    "Conversion": 		"20% of Physical Damage Converted to Lightning during Flask effect"
}


class FilterManager:
    def __init__(self):
        self.userFilters = []
        self.autoFilters = []
        self.compiledFilters = []
        self.activeFilters = []

        self.categories = {}
        self.price_threshold = '1 exalted'
        self.default_price_override = "* 1"
        self.price_overrides = {}
        self.state_overrides = {}

        self.filters_lock = threading.Lock()
        self.loadConfig()
        self.saveConfig()

    def loadConfig(self):
        try:
            with open(_FILTERS_CFG_FNAME, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            self.categories = data.get('categories', {})
            self.price_threshold = data.get('price_threshold', '1 exalted')
            self.default_price_override = data.get('default_price_override', 1)
            self.price_overrides = data.get('price_overrides', {})
            self.state_overrides = data.get('state_overrides', {})

            if not cm.isPriceValid(self.price_threshold):
                raise AppException(FM_INVALID_PRICE_THRESHOLD.format(self.price_threshold))

            self.validateOverrides()

        except FileNotFoundError:
            pass

    def saveConfig(self):
        data = {
            'default_price_override': self.default_price_override,
            'price_threshold': self.price_threshold,
            'categories': self.categories,
            'price_overrides': self.price_overrides,
            'state_overrides': self.state_overrides
        }

        with open(_FILTERS_CFG_FNAME, mode="w", encoding="utf-8", errors="replace") as f:
            json.dump(data, f, indent=4, separators=(',', ': '), sort_keys=True)

    def fetchFromAPI(self):
        try:
            filters = []
            c = pycurl.Curl()
            updateConfig = False
            for url in _URLS:
                furl = url.format(config.league)
                data = getJsonFromURL(furl, handle=c, max_attempts=3)
                if data is None:
                    raise AppException("Filters update failed. Bad response from server")

                category = re.match(".*Get(.*)Overview", furl).group(1).lower()

                if category not in self.categories:
                    self.categories[category] = True
                    updateConfig = True

                for item in data['lines']:
                    crit = {}
                    crit['price'] = "{} exalted".format(float(item.get('exaltedValue', 0)))
                    crit['name'] = [item['name'].lower()]
                    crit['type'] = [_ITEM_TYPE[item['itemClass']]]
                    crit['buyout'] = True

                    title = "{} {} {}".format(
                        'Legacy' if 'relic' in crit['type'] else '',
                        item['name'],
                        item['variant'] if item['variant'] is not None else '').strip()

                    if item['variant'] is not None:
                        if item['variant'] not in _VARIANTS:
                            msgr.send_msg("Unknown variant {} in item {}".format(item['variant'], item['name']),
                                          logging.WARN)
                        else:
                            crit['explicit'] = {'mods': [{'expr': _VARIANTS[item['variant']]}]}

                    #fltr.validate()
                    filters.append(Filter(title, crit, False, category, id=title.lower()))

            self.autoFilters = filters
            self.saveAutoFilters()

            if updateConfig:
                self.saveConfig()
        except pycurl.error as e:
            raise AppException("Filters update failed. Connection error: {}".format(e))
        except (KeyError, ValueError) as e:
            raise AppException("Filters update failed. Parsing error: {}".format(e))
        except Exception as e:
            logexception()
            raise AppException("Filters update failed. Unexpected error: {}".format(e))

    def loadUserFilters(self):
        try:
            self.userFilters = FilterManager.loadFiltersFromFile(_USER_FILTERS_FNAME)
        except AppException:
            raise
        except Exception as e:
            logexception()
            raise AppException("Loading user filters failed. Unexpected error: {}".format(e))

    def loadAutoFilters(self):
        try:
            self.autoFilters = FilterManager.loadFiltersFromFile(_AUTO_FILTERS_FNAME)
        except AppException:
            raise
        except Exception as e:
            logexception()
            raise AppException("Loading generated filters failed. Unexpected error: {}".format(e))

    def saveAutoFilters(self):
        with open(_AUTO_FILTERS_FNAME, mode="w", encoding="utf-8", errors="replace") as f:
            json.dump(self.autoFilters, f, indent=4, separators=(',', ': '), cls=FilterEncoder)

    def compileFilters(self):
        tamount, tshort = cm.priceFromString(self.price_threshold)
        min_val = cm.convert(float(tamount), tshort)

        disabled_cat = [cat for cat, enabled in self.categories.items() if not enabled]

        filters = []

        for fltr in self.autoFilters:
            comp = self.compileFilter(fltr)
            if comp is None:
                msgr.send_msg('Failed compiling filter {}'.format(fltr.getDisplayTitle()), logging.WARN)
            else:
                cf = CompiledFilter(fltr, comp)
                cf.enabled = comp.get('price', -1) >= min_val and fltr.category not in disabled_cat
                filters.append(cf)

        self.applyOverrides(filters)

        user_filters = []
        for fltr in self.userFilters:
            comp = self.compileFilter(fltr)
            if comp is None:
                msgr.send_msg('Failed compiling filter {}'.format(fltr.getDisplayTitle()), logging.WARN)
            else:
                cf = CompiledFilter(fltr, comp)
                cf.enabled = fltr.enabled and fltr.category not in disabled_cat
                user_filters.append(cf)

        filters = user_filters + filters

        active_filters = [fltr for fltr in filters if fltr.enabled]

        with self.filters_lock:
            self.activeFilters = active_filters
            self.compiledFilters = filters

    def applyOverrides(self, filters):
        for cf in filters:
            # title = re.match('(.+) \(.+\)', fltr.title.lower()).group(1)

            override = self.default_price_override
            for id in self.price_overrides:
                if id.lower() == cf.fltr.id:
                    override = self.price_overrides[id]
                    break

            state = cf.enabled
            for id in self.state_overrides:
                if id.lower() == cf.fltr.id:
                    state = self.state_overrides[id]

            cf.enabled = state
            cf.comp['price'] = Filter.compilePrice(override, cf.comp['price'])

            if cf.comp['price'] <= 0:
                cf.enabled = False

    def validateOverrides(self):
        for key, state in self.state_overrides.items():
            if not isinstance(state, bool):
                try:
                    self.state_overrides[key] = str2bool(str(state))
                except ValueError:
                    raise AppException("Invalid state override '{}' for {}. Must be a boolean.".format(state, key))

        if not Filter.isPriceValid(self.default_price_override):
            raise AppException("Invalid default price override {}".format(self.default_price_override))

        for key, override in self.price_overrides.items():
            if not Filter.isPriceValid(override):
                raise AppException("Invalid price override '{}' for {}".format(override, key))

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
                    return None
                baseComp = self.compileFilter(compiledFilter.fltr, path)
            else:
                baseComp = self.compileFilter(baseFilter, path)

        if baseComp is None:
            return None

        return fltr.compile(baseComp)

    @staticmethod
    def getFilterById(id, filters, match=lambda x, y: x.id == y):
        for fltr in filters:
            if match(fltr, id):
                return fltr
        return None

    @staticmethod
    def loadFiltersFromFile(fname):
        filters = []

        cur_fname = fname
        try:
            with open(cur_fname, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            cur_fname = _FILTER_SCHEMA_FNAME
            with open(cur_fname) as f:
                schema = json.load(f)

            # normalize keys and values
            data = lower_json(data)

            validate(data, schema)

            for item in data:
                fltr = Filter.fromDict(item)
                fltr.validate()
                filters.append(fltr)
        except FileNotFoundError:
            raise AppException(FILTER_FILE_MISSING.format(cur_fname))
        except ValidationError as e:
            raise AppException(FILTER_VALIDATION_ERROR.format(FilterManager._get_verror_msg(e, data)))
        except SchemaError as e:
            raise AppException(FILTER_SCHEMA_ERROR.format(e.message))
        except json.decoder.JSONDecodeError as e:
            raise AppException(FILTER_INVALID_JSON.format(e, cur_fname))

        return filters

    @staticmethod
    def _get_verror_msg(verror, data=None):
        pathMsg = ""
        for i, p in enumerate(verror.path):
            if isinstance(p, int):
                if i == 0:
                    pathMsg += "filter #{}".format(p + 1)
                    if data is not None:
                        filter_name = data[p].get("title", "")
                        if filter_name:
                            pathMsg += " ({})".format(filter_name)
                elif verror.path[i - 1] == "mods":
                    pathMsg += " > mod #{}".format(p + 1)
                elif verror.path[i - 1] == "values":
                    pathMsg += " > value #{}".format(p + 1)
            else:
                pathMsg += " > {}".format(p)

        if pathMsg:
            return "{} >>>> {}".format(verror.message, pathMsg)

        return verror.message

def lower_json(x):
    if isinstance(x, list):
        return [lower_json(v) for v in x]
    if isinstance(x, dict):
        d = {}
        for k, v in x.items():
            if k.lower() in ("title"):
                d[k.lower()] = v
            else:
                d[k.lower()] = lower_json(v)
        return d
        # return {k.lower(): lower_keys(v) for k, v in x.items()}
    if isinstance(x, str):
        return x.lower()
    return x