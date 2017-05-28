import json
import re
from array import array

from json import JSONEncoder
from lib.Utility import config, AppException
from lib.CurrencyManager import cm
from jsonschema import validate, ValidationError, SchemaError

_ITEM_TYPE = {0: 'normal',
              1: 'magic',
              2: 'rare',
              3: 'unique',
              4: 'gem',
              5: 'currency',
              6: 'divination card',
              7: 'quest item',
              8: 'prophecy',
              9: 'relic'}

_PRICE_REGEX = re.compile('\s*([0-9]+|[0-9]+\.[0-9]+)\s+([a-z]+)')
_BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")

FILTER_FILE_MISSING = "Missing file: {}"
FILTER_INVALID_JSON = "Error decoding JSON: {} in file {}"
FILTER_VALIDATION_ERROR = "Error validating filter: {}"
FILTER_SCHEMA_ERROR = "Filter schema error: {}"
FILTER_INVALID_PRICE = "Invalid price in filter: {}"
FILTER_INVALID_REGEX = "Invalid regex: {}, error: {}"


class FilterDecoder(JSONEncoder):
    RE_COMPILED = type(re.compile(''))

    def default(self, o):
        if isinstance(o, FilterDecoder.RE_COMPILED):
            return o.pattern
        return json.JSONEncoder.default(self, o)


class Filter:

    FILTER_FNAME = "cfg\\filters.json"
    FILTER_SCHEMA_FNAME = "cfg\\filters.schema.json"

    def __init__(self, criteria):
        self.criteria = criteria

    def __str__(self):
        # return self.criteria.__str__()
        return json.dumps(self.criteria, sort_keys=True, cls=FilterDecoder)

    def checkItem(self, item, stash):
        for key in self.criteria:
            if key == "base" and self.criteria[key] not in item["typeLine"].lower():
                return False
            if key == "ilvl" and self.criteria[key] > item["ilvl"]:
                return False
            if key == "corrupted" and self.criteria[key] != item["corrupted"]:
                return False
            if key == "crafted" and self.criteria[key] != "craftedMods" in item:
                return False
            if key == "type" and _ITEM_TYPE[item["frameType"]] not in self.criteria[key]:
                return False
            if key == "sockets" and self.criteria[key] > get_item_sockets(item):
                return False
            if key == "links" and self.criteria[key] > get_item_links(item):
                return False
            if key == "stacksize" and self.criteria[key] > get_item_stacksize(item):
                return False

        for key in self.criteria:
            if key == "buyout" and self.criteria[key] != get_item_buyout(item, stash):
                return False
            if key == "price":
                price = get_item_price(item, stash)
                if price is not None:
                    amount, currency = price
                    if cm.convert(float(amount), currency) > cm.convert(*self.criteria[key]):
                        return False

            if key == "name":
                if not any(name in get_item_name(item).lower() for name in self.criteria[key]):
                    return False

        for key in self.criteria:
            if key == "implicit":
                mods = [mod.lower() for mod in item.get("implicitMods", [])]
                if len(self.criteria[key]) > len(mods): return False
                for mod_regex in self.criteria[key]:
                    if not Filter._checkmod(mod_regex['expr'], mod_regex.get('values', []), mods):
                        return False

            if key == "explicit":
                mods = [mod.lower() for mod in item.get("explicitMods", [])]
                if len(self.criteria[key]) > len(mods): return False
                for mod_regex in self.criteria[key]:
                    if not Filter._checkmod(mod_regex['expr'], mod_regex.get('values', []), mods):
                        return False

            if key == "mods":
                mods = []
                for key_name in ("implicitMods", "explicitMods", "craftedMods", "enchantMods"):
                    mods += item.get(key_name, [])

                if len(self.criteria[key]) > len(mods): return False
                mods = [mod.lower() for mod in mods]
                for mod_regex in self.criteria[key]:
                    if not Filter._checkmod(mod_regex['expr'], mod_regex.get('values', []), mods):
                        return False

        return True

    @staticmethod
    def _checkmod(regex, filter_vals, mods):
        for mod in mods:
            match = regex.match(mod)
            if match is not None:
                if len(filter_vals) == 0:
                    return True

                elif len(filter_vals) == 1:
                    sum = 0
                    for mod_val in match.groups():
                        sum += float(mod_val)

                    if sum/len(match.groups()) >= filter_vals[0]:
                        return True

                elif len(filter_vals) > 1 and len(filter_vals) == len(match.groups()):
                    matched = True
                    for i, mod_val in enumerate(match.groups()):
                        if filter_vals[i] > mod_val:
                            matched = False
                            break

                    if matched:
                        return True

                # Maybe return false here, since if the pattern matched but value check failed it won't match again
                # return False

        return False

    def getTitle(self):
        return self.criteria.get("title", "Unnamed Filter")

    @staticmethod
    def loadfilters():
        filters = []

        try:
            fname = Filter.FILTER_FNAME
            with open(Filter.FILTER_FNAME) as f:
                data = json.load(f)

            fname = Filter.FILTER_SCHEMA_FNAME
            with open(Filter.FILTER_SCHEMA_FNAME) as f:
                schema = json.load(f)

            # normalize keys and values
            data = lower_json(data)

            validate(data, schema)

            for fltr in data:
                if 'price' in fltr:
                    price_valid = False
                    match = _PRICE_REGEX.match(fltr['price'])
                    if match is not None:
                        amount, currency = match.group(1, 2)
                        if currency in cm.whisper:  # cm.shorts
                            price_valid = True
                            fltr['price'] = (float(amount), currency)

                    if not price_valid:
                        raise AppException(FILTER_INVALID_PRICE.format(fltr['price']))

                for regex in fltr.get('mods', []):
                    regex['expr'] = re.compile(regex['expr'])

                for regex in fltr.get('implicit', []):
                    regex['expr'] = re.compile(regex['expr'])

                for regex in fltr.get('explicit', []):
                    regex['expr'] = re.compile(regex['expr'])

                filters.append(Filter(fltr))

        except re.error as e:
            raise AppException(FILTER_INVALID_REGEX.format(e.pattern, e))
        except ValidationError as e:
            # if e.validator == "required":
            raise AppException(FILTER_VALIDATION_ERROR.format(e.message))
        except SchemaError as e:
            raise AppException(FILTER_SCHEMA_ERROR.format(e.message))
        except json.decoder.JSONDecodeError as e:
            raise AppException(FILTER_INVALID_JSON.format(e, fname))
        except FileNotFoundError:
            raise AppException(FILTER_FILE_MISSING.format(fname))

        return filters

def get_item_price_raw(item, stash):
    price = None
    if "note" in item:
        price = item["note"]
    elif stash["stash"].startswith("~b/o ") or stash["stash"].startswith("~price "):
    #elif PRICE_REGEX.match(stash["stash"]):
        price = stash["stash"]

    return price


def get_item_sockets(item):
    return len(item["sockets"])


def get_item_links(item):
    if item["sockets"]:
        groups = array('I', [0]) * 6
        for socket in item["sockets"]:
            groups[socket["group"]] += 1

        return max(groups)
    return 0


def get_item_name(item):
    return _LOCALIZATION_REGEX.sub('', "{} {}".format(item["name"], item["typeLine"])).strip()


def get_item_buyout(item, stash):
    price = get_item_price_raw(item, stash)
    if price is not None:
        match = _BO_PRICE_REGEX.match(price.lower())

        if match is not None:
            return float(match.group(2)) > 0
    return False


def get_item_stacksize(item):
    return item.get("stackSize", 1)


def get_item_price(item, stash):
    # Returns tuple (amount, currency)

    price = get_item_price_raw(item, stash)
    if price is not None:
        match = _BO_PRICE_REGEX.match(price.lower())

        if match is not None:
            return match.group(2, 3)

    return None

def get_item_price_display(item, stash):
    # Returns format of {amount} {currency}

    price = get_item_price(item, stash)
    if price is not None:
        amount, currency = price
        return "{} {}".format(amount, cm.whisper[currency] if currency in cm.whisper else currency)

    return ""

def get_whisper_msg(item, stash):
    template = "@{} Hi, I would like to buy your {}{} listed{} in {} (stash tab \"{}\"; position: left {}, top {})"

    price_str = get_item_price_display(item, stash)
    if price_str != "":
        price_str = " for " + price_str

    size = get_item_stacksize(item)
    stack_size_str = "" if size == 1 else str(size) + " "

    return template.format(stash["lastCharacterName"], stack_size_str, get_item_name(item),
                           price_str, item["league"], stash["stash"],
                           item["x"] + 1, item["y"] + 1)


def get_item_info(item, stash):
    template = "Name: {}, ilvl: {}, Corrupted: {}, Sockets: {}, Links: {}, Price: {}, Stack: {}, Account: {}, Implicit: {}"

    price = get_item_price_raw(item, stash)
    if price is None:
        price = "n/a"

    return template.format(get_item_name(item), item["ilvl"], item["corrupted"], get_item_sockets(item),
                           get_item_links(item), price, get_item_stacksize(item), stash["accountName"], item.get("implicitMods", []))


def parse_stashes(data, filters, stateMgr, resultHandler):
    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == config.league:
            for item in stash["items"]:
                for fltr in filters:
                    if fltr.checkItem(item, stash):
                        if stateMgr.addItem(item["id"], get_item_price_raw(item, stash), stash["accountName"]):
                            resultHandler(item, stash, fltr)
                        break

    parse_next_id(data, stateMgr)


def parse_next_id(data, stateMgr):
    stateMgr.saveState(data["next_change_id"])


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