import re
from array import array

from lib.Utility import config, AppException
from lib.CurrencyManager import cm

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

_CURRENCY_DISPLAY = {'alt': 'alternation',
                     'fuse': 'fusing',
                     'alch': 'alchemy',
                     'exa': 'exalted',
                     'exalt': 'exalted',
                     'chrom': 'chromatic',
                     'jew': 'jewellers',
                     'chance': 'chance',
                     'scour': 'scouring',
                     'chaos': 'chaos',
                     'blessed': 'blessed',
                     'regret': 'regret',
                     'regal': 'regal',
                     'divine': 'divine',
                     'vaal': 'vaal',
                     'chisel': 'chisel',
                     'gcp': 'gcp',
                     'mir': 'mirror',
                     'kal': 'mirror',
                     'other': 'other'}

_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")

FILTER_FILE_MISSING = "Filter file was not found: {}"
FILTER_INVALID_ATTRIBUTE = "Unknown attribute: {} in filter {}"
FILTER_INVALID_CURRENCY_TYPE = "Invalid currency type in filter attribute {}"
FILTER_INSUFFICIENT_VALUES = "Not enough values in filter attribute: {}. expected one or more"
FILTER_INVALID_ITEM_TYPE = "Invalid item type in filter attribute {}"
FILTER_EXTRA_VALUES = "Too many values in filter attribute: {} expected 1. ignoring exceeding args"
FILTER_INVALID_VALUE_TYPE = "Invalid value type in filter field {}, expected type {}"
FILTER_INVALID_REGEX = "Invalid regex: {}, error: {}"


class Filter:

    filter_args = {'ilvl': int, 'buyout': bool, 'type': str, 'base': str, 'sockets': int, 'links': int, 'title': str,
                   'price': dict, 'corrupted': bool, 'crafted': bool, 'name': str,
                   'implicit': str, 'explicit': str, 'mods': str, 'stacksize': int}
    FILTER_FNAME = "cfg\\filters.cfg"

    def __init__(self, criteria):
        self.criteria = criteria

    def __str__(self):
        return self.criteria.__str__()

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
                # price = get_item_price_display(item, stash)
                # if price != "":
                #     amount, currency = price.split()
                #     if currency in self.criteria[key]:
                #         if float(amount) > self.criteria[key][currency]: return False
                #     elif "other" in self.criteria[key]:
                #         if float(amount) > self.criteria[key]["other"]: return False
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
                    if not Filter._checkmod(mod_regex[0], mod_regex[1:], mods):
                        return False

            if key == "explicit":
                mods = [mod.lower() for mod in item.get("explicitMods", [])]
                if len(self.criteria[key]) > len(mods): return False
                for mod_regex in self.criteria[key]:
                    if not Filter._checkmod(mod_regex[0], mod_regex[1:], mods):
                        return False

            if key == "mods":
                mods = []
                for key_name in ("implicitMods", "explicitMods", "craftedMods", "enchantMods"):
                    mods += item.get(key_name, [])

                if len(self.criteria[key]) > len(mods): return False
                mods = [mod.lower() for mod in mods]
                for mod_regex in self.criteria[key]:
                    if not Filter._checkmod(mod_regex[0], mod_regex[1:], mods):
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
            with open(Filter.FILTER_FNAME) as f:
                line = f.readline()
                while line:
                    fltr = Filter.fromString(line)

                    if fltr is not None:
                        filters.append(fltr)

                    line = f.readline()
        except FileNotFoundError:
            raise AppException(FILTER_FILE_MISSING.format(Filter.FILTER_FNAME))

        return filters

    @staticmethod
    def fromString(str):
        str = str.split(sep='#')[0].strip()

        fields = filter(None, str.split(','))

        crit = {}
        for field in fields:
            # clear those pesky whitespaces
            atts = [att.strip() for att in field.lower().split(':')]

            if atts[0] not in Filter.filter_args:
                raise AppException(FILTER_INVALID_ATTRIBUTE.format(atts[0], str))

            if len(atts) == 1:
                crit[atts[0]] = True

            elif len(atts) >= 2:
                if atts[0] == 'price':
                    try:
                        amount, currency = atts[1].strip().split()
                        amount = float(amount)
                        if currency not in cm.whisper:  # cm.shorts
                            raise ValueError

                        crit[atts[0]] = (amount, currency)

                        # prices = {}
                        # for att in atts[1:]:
                        #     amount, currency = att.strip().split()
                        #     amount = float(amount)
                        #     if currency not in _CURRENCY_DISPLAY.values():
                        #         raise ValueError
                        #
                        #     prices[currency] = amount
                        # crit[atts[0]] = prices
                    except ValueError:
                        raise AppException(FILTER_INVALID_CURRENCY_TYPE.format(field))
                elif atts[0] == 'name':
                    crit[atts[0]] = [name for name in atts[1:]]
                    if not len(crit[atts[0]]):
                        raise AppException(FILTER_INSUFFICIENT_VALUES.format(field))
                elif atts[0] == 'type':
                    types = []
                    for item_type in atts[1:]:
                        if item_type not in _ITEM_TYPE.values():
                            raise AppException(FILTER_INVALID_ITEM_TYPE.format(field))
                        types.append(item_type)
                    if len(types):
                        crit[atts[0]] = types
                    else:
                        raise AppException(FILTER_INSUFFICIENT_VALUES.format(field))
                elif atts[0] in ('implicit', 'explicit', 'mods'):
                    regexes = []

                    for mod in atts[1:]:
                        mod_fields = mod.split(';')

                        l = [float(num) for num in mod_fields[1:]]

                        try:
                            l.insert(0, re.compile(mod_fields[0]))
                        except re.error as e:
                            raise AppException(FILTER_INVALID_REGEX.format(mod_fields[0], e))
                        regexes.append(l)

                    crit[atts[0]] = regexes
                else:
                    try:
                        if Filter.filter_args[atts[0]] == bool:
                            crit[atts[0]] = str2bool(atts[1])
                        else:
                            # 'hack' to get original title
                            if atts[0] == 'title':
                                crit[atts[0]] = field.split(':')[1].strip()
                            else:
                                crit[atts[0]] = Filter.filter_args[atts[0]](atts[1])

                        if len(atts) > 2:
                            print(FILTER_EXTRA_VALUES.format(field))
                    except ValueError:
                        raise AppException(FILTER_INVALID_VALUE_TYPE
                                           .format(field, Filter.filter_args[atts[0]].__name__))

        if not len(crit):
            return None

        return Filter(crit)


def str2bool(str):
    if str.lower() in ("true", "t", "yes", "y", "1"): return True
    if str.lower() in ("false", "f", "no", "n", "0"): return False
    raise ValueError


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
        match = _PRICE_REGEX.match(price.lower())

        if match is not None:
            return float(match.group(2)) > 0
    return False


def get_item_stacksize(item):
    return item.get("stackSize", 1)


def get_item_price(item, stash):
    # Returns tuple (amount, currency)

    price = get_item_price_raw(item, stash)
    if price is not None:
        match = _PRICE_REGEX.match(price.lower())

        if match is not None:
            return match.group(2, 3)

    return None

def get_item_price_display(item, stash):
    # Returns format of {amount} {currency}

    price = get_item_price(item, stash)
    if price is not None:
        amount, currency = price
        # return "{} {}".format(amount, _CURRENCY_DISPLAY[currency] if currency in _CURRENCY_DISPLAY else currency)
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
    template = "Name: {}, ilvl: {}, Corrupted: {}, Sockets: {}, Links: {}, Price: {}, Stack: {}, Account: {}"

    price = get_item_price_raw(item, stash)
    if price is None:
        price = "n/a"

    return template.format(get_item_name(item), item["ilvl"], item["corrupted"], get_item_sockets(item),
                           get_item_links(item), price, get_item_stacksize(item), stash["accountName"])


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
