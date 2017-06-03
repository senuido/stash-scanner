import json
import re
from array import array

from json import JSONEncoder
from lib.Utility import config, AppException
from lib.CurrencyManager import cm
from jsonschema import validate, ValidationError, SchemaError

_FILTER_PRIO = {
    "base": 1,
    "price": 1,
    "ilvl": 1,
    "corrupted": 1,
    "crafted": 1,
    "type": 1,
    "sockets": 1,
    "stacksize": 1,
    "modcount_min": 1,
    "modcount_max": 1,
    "buyout": 1,

    "links": 2,
    "name": 2,

    "implicit": 3,
    "explicit": 4,
    "mods": 4,
}

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
_NUMBER_REGEX = re.compile('[0-9]+(?:\.[0-9]+)?')
_PRICE_REGEX = re.compile('\s*([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")

FILTER_INVALID_PRICE = "Invalid price in filter: {}"
FILTER_INVALID_REGEX = "Invalid regex: {}, error: {}"


class FilterEncoder(JSONEncoder):
    RE_COMPILED = type(re.compile(''))

    def default(self, o):
        if isinstance(o, FilterEncoder.RE_COMPILED):
            return o.pattern
        if isinstance(o, Filter):
            return {
                'title': o.title,
                'enabled': o.enabled,
                'category': o.category,
                'criteria': o.criteria}
        return json.JSONEncoder.default(self, o)


class Filter:

    def __init__(self, title, criteria):
        self.title = title
        self.criteria = criteria
        self.enabled = True
        self.category = "user"

        self.comp = {}
        self.crit_ordered = []

        #self.Init()

    def __str__(self):
        # return self.criteria.__str__()
        #return "{}: {}".format(self.title, json.dumps(self.criteria, sort_keys=True, cls=FilterEncoder))
        text = "{}: ".format(self.title)
        if 'price' in self.criteria:
            price = cm.priceFromString(self.criteria['price'])
            text += " Price: {}, Chaos Price: {}, New Price: {}"\
                .format(self.criteria['price'],
                        round(cm.convert(float(price[0]), price[1]), 0),
                        round(self.comp['price'], 0))
        return text

    def Init(self):
        crit = self.criteria

        try:
            for mod_key in ("implicit", "explicit", "mods"):
                if mod_key in crit:
                    mods = crit[mod_key]
                    for regex in mods['mods']:
                        regex['expr'] = re.compile(regex['expr'])
                        regex['required'] = regex.get('required', False)
                        regex['values'] = regex.get('values', [])

                    if 'match_min' not in mods and 'match_max' not in mods:
                        mods['match_min'] = len(mods['mods'])
                        mods['match_max'] = len(mods['mods'])
                    elif 'match_max' in mods and 'match_min' not in mods:
                        mods['match_min'] = 0
                    elif 'match_min' in mods and 'match_max' not in mods:
                        mods['match_max'] = len(mods['mods'])

                    mods['mods'] = sorted(mods['mods'], key=lambda k: k['required'], reverse=True)
        except re.error as e:
            raise AppException(FILTER_INVALID_REGEX.format(e.pattern, e))

        if 'type' in crit:
            types = []
            for itype in crit['type']:
                for id in _ITEM_TYPE:
                    if itype == _ITEM_TYPE[id]:
                        types.append(id)
                        break
            self.comp['type'] = types

        if 'price' in crit:
            price_valid = False
            price = cm.priceFromString(crit['price'])
            if price is not None:
                amount, currency = price
                if currency in cm.whisper:  # cm.shorts
                    price_valid = True
                    self.comp['price'] = cm.convert(float(amount), currency)

            if not price_valid:
                raise AppException(FILTER_INVALID_PRICE.format(crit['price']))

        self.crit_ordered = sorted(crit.keys(), key=lambda k: _FILTER_PRIO[k])

    @classmethod
    def fromData(cls, title, criteria, category, enabled=True):
        flt = cls(title, criteria)
        flt.category = category
        flt.enabled = enabled

        return flt

    def checkItem(self, item):
        for key in self.crit_ordered:
            if key == "type" and item.type not in self.comp[key]:
                return False
            if key == "price":
                if item.price is not None and item.price > self.comp[key]:
                        return False
            elif key == "name":
                if not any(name in item.name for name in self.criteria[key]):
                    return False
            elif key == "base" and self.criteria[key] not in item.base:
                return False
            elif key == "ilvl" and self.criteria[key] > item.ilvl:
                return False
            elif key == "corrupted" and self.criteria[key] != item.corrupted:
                return False
            elif key == "crafted" and self.criteria[key] != item.crafted:
                return False
            elif key == "sockets" and self.criteria[key] > item.sockets:
                return False
            elif key == "links" and self.criteria[key] > item.links:
                return False
            elif key == "stacksize" and self.criteria[key] > item.stacksize:
                return False
            elif key == "modcount_min" and self.criteria[key] > item.modcount:
                return False
            elif key == "modcount_max" and self.criteria[key] < item.modcount:
                return False
            elif key == "buyout" and self.criteria[key] != item.buyout:
                return False
            elif key == "implicit":
                if not Filter._checkmods(self.criteria[key]['mods'], item.implicit, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False
            elif key == "explicit":
                if not Filter._checkmods(self.criteria[key]['mods'], item.explicit, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False
            elif key == "mods":
                if not Filter._checkmods(self.criteria[key]['mods'], item.mods, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False

        return True

    def checkItemOld(self, item, stash):
        for key in self.criteria:
            if key == "base" and self.criteria[key] not in item["typeLine"].lower():
                return False
            elif key == "ilvl" and self.criteria[key] > item["ilvl"]:
                return False
            elif key == "corrupted" and self.criteria[key] != item["corrupted"]:
                return False
            elif key == "crafted" and self.criteria[key] != "craftedMods" in item:
                return False
            elif key == "type" and _ITEM_TYPE[item["frameType"]] not in self.criteria[key]:
                return False
            elif key == "sockets" and self.criteria[key] > get_item_sockets(item):
                return False
            elif key == "links" and self.criteria[key] > get_item_links(item):
                return False
            elif key == "stacksize" and self.criteria[key] > get_item_stacksize(item):
                return False
            elif key == "modcount_min" and self.criteria[key] > get_item_modcount(item):
                return False
            elif key == "modcount_max" and self.criteria[key] < get_item_modcount(item):
                return False

        for key in self.criteria:
            if key == "buyout" and self.criteria[key] != get_item_buyout(item, stash):
                return False

            elif key == "price":
                price = get_item_price(item, stash)
                if price is not None:
                    amount, currency = price
                    if cm.convert(float(amount), currency) > cm.convert(*self.criteria[key]):
                        return False

            elif key == "name":
                if not any(name in get_item_name(item).lower() for name in self.criteria[key]):
                    return False

        for key in self.criteria:
            if key == "implicit":
                mods = [mod.lower() for mod in item.get("implicitMods", [])]
                if not Filter._checkmods(self.criteria[key]['mods'], mods, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False

            elif key == "explicit":
                mods = [mod.lower() for mod in item.get("explicitMods", [])]
                if not Filter._checkmods(self.criteria[key]['mods'], mods, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False

            elif key == "mods":
                mods = []
                for key_name in ("implicitMods", "explicitMods", "craftedMods", "enchantMods"):
                    mods += item.get(key_name, [])

                mods = [mod.lower() for mod in mods]
                if not Filter._checkmods(self.criteria[key]['mods'], mods, self.criteria[key]['match_min'], self.criteria[key]['match_max']):
                    return False

        return True

    def getDisplayTitle(self):
        if self.category == 'user' or 'price' not in self.comp:
            return self.title

        ex_val = cm.convert(1, 'exalted')

        if 0 < ex_val <= self.comp['price']:
            price = '{:.2f} ex'.format(self.comp['price']/ex_val)
        else:
            price = '{:.0f}c'.format(self.comp['price'])

        return "{} ({})".format(self.title, price)

    @staticmethod
    def _checkmods(exprs, mods, match_min, match_max):

        mods = list(mods)

        if match_min > len(mods) or match_max < match_min:
            return False

        matched = 0
        for mod_expr in exprs:
            expr_matched = False

            expr = mod_expr['expr']
            vals = mod_expr['values']
            req = mod_expr['required']

            for mod in mods:
                if Filter._checkexpr(expr, vals, mod):
                    expr_matched = True
                    mods.remove(mod)  # ok since we're only removing one
                    break

            if expr_matched:
                matched += 1

                if matched > match_max:
                    return False

                if matched >= match_min:
                    return True
            elif req:
                return False

        return match_min <= matched <= match_max

    @staticmethod
    def _checkexpr(expr, vals, mod):
        match = expr.match(mod)
        if match is not None:
            if len(vals) == 0:
                return True

            elif len(vals) == 1:
                sum = 0
                for mod_val in match.groups():
                    sum += float(mod_val)

                if sum / len(match.groups()) >= vals[0]:
                    return True

            elif len(vals) > 1 and len(vals) == len(match.groups()):
                matched = True
                for i, mod_val in enumerate(match.groups()):
                    if vals[i] > mod_val:
                        matched = False
                        break

                if matched:
                    return True
        return False

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


def get_item_modcount(item):
    return len(item.get('explicitMods', [])) + len(item.get('implicitMods', [])) + len(item.get('craftedMods', []))


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
    template = "{}{}: ilvl: {}, Links: {}, Implicit: {}, Explicit: {}, Price: {}, Stack: {}, Account: {}, " \
               "Sockets: {}"

    price = get_item_price_raw(item, stash)
    if price is None:
        price = "n/a"

    return template.format("!!! CORRUPTED !!! " if item["corrupted"] else "",
                           get_item_name(item), item["ilvl"],
                           get_item_links(item), item.get("implicitMods", []), item.get("explicitMods", []),
                           price, get_item_stacksize(item), stash["accountName"], get_item_sockets(item))


def parse_stashes(data, filters, stateMgr, resultHandler):
    league_tabs = 0
    item_count = 0
    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == config.league:
            league_tabs += 1
            item_count += len(stash["items"])
            for item in stash["items"]:
                curItem = Item(item, stash)
                for fltr in filters:
                    if fltr.checkItem(curItem):
                        if stateMgr.addItem(item["id"], get_item_price_raw(item, stash), stash["accountName"]):
                            resultHandler(item, stash, fltr)
                        break

    parse_next_id(data, stateMgr)
    return len(data["stashes"]), league_tabs, item_count


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


class Item:
    def __init__(self, item, stash):
        self.links = get_item_links(item)
        self.sockets = get_item_sockets(item)
        self.corrupted = item['corrupted']
        self.ilvl = item['ilvl']
        self.base = item['typeLine'].lower()
        self.crafted = 'craftedMods' in item
        # self.type = _ITEM_TYPE[item['frameType']]
        self.type = item['frameType']
        self.stacksize = get_item_stacksize(item)
        self.modcount = get_item_modcount(item)

        self.name = get_item_name(item)
        price = get_item_price(item, stash)
        if price is None:
            self.price = None
        else:
            self.price = cm.convert(float(price[0]), price[1])
        self.buyout = self.price is not None and self.price > 0

        self.implicit = [mod.lower() for mod in item.get('implicitMods', [])]
        self.explicit = [mod.lower() for mod in item.get('explicitMods', [])]
        self.mods = self.implicit + self.explicit + \
                    [mod.lower() for mod in (item.get('enchantMods', []) + item.get('craftedMods', []))]

