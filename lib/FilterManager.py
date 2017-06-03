import json

import re

import pycurl
from jsonschema import validate, ValidationError, SchemaError
from lib.Utility import config, AppException, getJsonFromURL
from lib.CurrencyManager import cm
from lib.ItemHelper import Filter, _ITEM_TYPE, FilterEncoder

_OVERRIDE_REGEX = re.compile('\s*([+\-=]?)\s*(.+)')
_NUMBER_REGEX = re.compile('[0-9]+(?:\.[0-9]+)?$')

FILTER_FILE_MISSING = "Missing file: {}"
FILTER_INVALID_JSON = "Error decoding JSON: {} in file {}"
FILTER_VALIDATION_ERROR = "Error validating filter: {}"
FILTER_SCHEMA_ERROR = "Filter schema error: {}"

FM_INVALID_PRICE_THRESHOLD = "Invalid price threshold {}"

_AUTO_FILTERS_FNAME = "tmp\\auto-filters.json"
_FILTERS_CFG_FNAME = "cfg\\filters-config.json"
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

        self.categories = {}
        self.overrides = {}
        self.default_override = 0.9
        self.price_threshold = '1 exalted'

        self.loadConfig()

    def loadConfig(self):
        try:
            with open(_FILTERS_CFG_FNAME, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            self.categories = data['categories']
            self.overrides = data['overrides']
            self.default_override = data['default_override']
            self.price_threshold = data['price_threshold']

            if not cm.isPriceValid(self.price_threshold):
                raise AppException(FM_INVALID_PRICE_THRESHOLD.format(self.price_threshold))

            self.validateOverrides()

        except FileNotFoundError:
            pass

    def saveConfig(self):
        data = {
            'default_override': self.default_override,
            'price_threshold': self.price_threshold,
            'categories': self.categories,
            'overrides': self.overrides
        }

        #os.makedirs(os.path.dirname(_AUTO_CFG_FNAME), exist_ok=True)
        with open(_FILTERS_CFG_FNAME, mode="w", encoding="utf-8", errors="replace") as f:
            json.dump(data, f, indent=4, separators=(',', ': '), sort_keys=False)

    def fetchFromAPI(self):
        try:
            filters = []

            for url in _URLS:
                furl = url.format(config.league)
                data = getJsonFromURL(furl)

                category = re.match(".*Get(.*)Overview", furl).group(1).lower()

                if category not in self.categories:
                    self.categories[category] = True

                for item in data['lines']:
                    crit = {}
                    crit['price'] = "{} exalted".format(float(item['exaltedValue']))
                    crit['name'] = [item['name']]
                    crit['type'] = [_ITEM_TYPE[item['itemClass']]]
                    crit['buyout'] = True

                    title = "{} {} {}".format(
                        'Legacy' if crit['type'] == 'relic' else '',
                        item['name'],
                        item['variant'] if item['variant'] is not None else '').strip()

                    if item['variant'] is not None:
                        if item['variant'] not in _VARIANTS:
                            print("Unknown variant {} in item {}".format(item['variant'], item['name']))
                        else:
                            crit['explicit'] = {'mods': [{'expr': _VARIANTS[item['variant']]}]}

                    filters.append(Filter.fromData(title, crit, category, False))

            self.autoFilters = filters
            self.saveAutoFilters()
            self.initAutoFilters()
            self.saveConfig()
        except pycurl.error as e:
            raise AppException("Filters update failed. Connection error: {}".format(e))
        except (KeyError, ValueError) as e:
            raise AppException("Filters update failed. Parsing error: {}".format(e))
        except Exception as e:
            # WRITE TO FILE FOR DEBUG
            raise AppException("Filters update failed. Unexpected error: {}".format(e))

    def loadUserFilters(self):
        try:
            self.userFilters = FilterManager.loadFiltersFromFile(_USER_FILTERS_FNAME)
        except Exception as e:
            raise AppException("Loading user filters failed. Unexpected error: {}".format(e))

    def loadAutoFilters(self):
        try:
            self.autoFilters = FilterManager.loadFiltersFromFile(_AUTO_FILTERS_FNAME)
            self.initAutoFilters()
        except AppException:
            raise
        except Exception as e:
            self.autoFilters = []
            raise AppException("Loading generated filters failed. Unexpected error: {}".format(e))

    def saveAutoFilters(self):
        with open(_AUTO_FILTERS_FNAME, mode="w", encoding="utf-8", errors="replace") as f:
            json.dump(self.autoFilters, f, indent=4, separators=(',', ': '), cls=FilterEncoder)

    def initAutoFilters(self):
        tamount, tshort = cm.priceFromString(self.price_threshold)
        min_val = cm.convert(float(tamount), tshort)

        disabled_cat = [cat for cat, enabled in self.categories.items() if not enabled]

        for fltr in self.autoFilters:
            fltr.Init()

            # enable if above threshold and not in disabled category
            # fltr.enabled = cm.convert(*fltr.criteria['price']) >= min_val and fltr.category not in disabled_cat
            fltr.enabled = fltr.comp['price'] >= min_val and fltr.category not in disabled_cat

        self.applyOverrides()

    def applyOverrides(self):
        for fltr in self.autoFilters:
            override = self.default_override

            # title = re.match('(.+) \(.+\)', fltr.title.lower()).group(1)
            for flt_name in self.overrides:
                if flt_name.lower() == fltr.title.lower():
                    override = self.overrides[flt_name]
                    break

            # get filter price in chaos
            # flt_price_val = cm.convert(*fltr.criteria['price'])
            flt_price_val = fltr.comp['price']

            # get opr
            opr, price = _OVERRIDE_REGEX.match(str(override)).groups()
            new_price = 0

            # factor
            if opr == '':
                new_price = flt_price_val * float(price)
            else:
                # get override value
                amount, short = cm.priceFromString(price)
                override_val = cm.convert(float(amount), short)

                if opr == '+':
                    new_price = flt_price_val + override_val
                elif opr == '-':
                    new_price = flt_price_val - override_val
                elif opr == '=':
                    new_price = override_val

            # fltr.criteria['price'] = (round(new_price, 2), 'chaos')
            fltr.comp['price'] = round(new_price, 2)

            if new_price <= 0:
                fltr.enabled = False

    def validateOverrides(self):
        if not self.isOverrideValid("default", self.default_override):
            raise AppException("Invalid default filter override {}".format(self.default_override))

        for key, override in self.overrides.items():
            if not self.isOverrideValid(key, override):
                raise AppException("Invalid filter override {} for {}".format(override, key))

    def getFilters(self):
        return self.userFilters + self.autoFilters

    def getEnabledFilters(self):
        return [fltr for fltr in self.getFilters() if fltr.enabled]

    @staticmethod
    def isOverrideValid(flt_name, override):
        match = _OVERRIDE_REGEX.match(str(override))
        if match is not None:
            opr, price = match.groups()
            if opr == '': return _NUMBER_REGEX.match(price) is not None
            else: return cm.isPriceValid(price)
        return False

    @staticmethod
    def loadFiltersFromFile(fname):
        filters = []

        try:
            cur_fname = fname
            with open(cur_fname, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            cur_fname = _FILTER_SCHEMA_FNAME
            with open(cur_fname) as f:
                schema = json.load(f)

            # normalize keys and values
            data = lower_json(data)

            validate(data, schema)

            for item in data:
                # if not item.get('enabled', True):
                #     continue

                fltr = Filter(item['title'], item['criteria'])
                fltr.Init()

                filters.append(fltr)

        except ValidationError as e:
            raise AppException(FILTER_VALIDATION_ERROR.format(FilterManager._get_verror_msg(e, data)))
        except SchemaError as e:
            raise AppException(FILTER_SCHEMA_ERROR.format(e.message))
        except json.decoder.JSONDecodeError as e:
            raise AppException(FILTER_INVALID_JSON.format(e, cur_fname))
        except FileNotFoundError:
            raise AppException(FILTER_FILE_MISSING.format(cur_fname))

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