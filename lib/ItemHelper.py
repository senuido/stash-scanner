import copy
import json
import re
from array import array
from enum import IntEnum
from itertools import chain

from json import JSONEncoder
from lib.Utility import config, AppException
from lib.CurrencyManager import cm
from jsonschema import validate, ValidationError, SchemaError
from joblib import Parallel, delayed, cpu_count

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

_BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")


class FilterEncoder(JSONEncoder):
    RE_COMPILED = type(re.compile(''))

    def default(self, o):
        if isinstance(o, FilterEncoder.RE_COMPILED):
            return o.pattern
        if isinstance(o, Filter):
            return o.toDict()
        return json.JSONEncoder.default(self, o)


class CompiledFilter:
    def __init__(self, fltr, comp):
        self.fltr = fltr
        self.comp = comp
        self.enabled = fltr.enabled

        self.crit_ordered = sorted(comp.keys(), key=lambda k: _FILTER_PRIO[k])

    def __str__(self):
        # return "{}: {}".format(self.title, json.dumps(self.criteria, sort_keys=True, cls=FilterEncoder))
        # if 'price' in self.fltr.criteria:
        # if self.fltr.category == 'user':
        #     return "{}: {}".format(self.getDisplayTitle(), json.dumps(self.comp, sort_keys=True, cls=FilterEncoder))
        return self.getDisplayTitle()

    def getDisplayPrice(self):
        if 'price' not in self.comp:  # or self.comp['price'] <= 0:
            return ''

        ex_val = cm.convert(1, 'exalted')
        if 0 < ex_val <= self.comp['price']:
            val = round(self.comp['price'] / ex_val, 2)
            if val == int(val): val = int(val)
            price = '{} ex'.format(val)
        else:
            price = '{:.0f}c'.format(self.comp['price'])

        return price

    def getDisplayTitle(self):
        title = self.fltr.title
        # if self.fltr.category != 'user':
        price = self.getDisplayPrice()

        if price:
            title = "{} ({})".format(self.fltr.title, price)

        return title

    def checkItem(self, item):
        for key in self.crit_ordered:
            if key == "type" and item.type not in self.comp[key]:
                return False
            if key == "price":
                if item.price is not None and item.price > self.comp[key]:
                        return False
            elif key == "name":
                if not any(name in item.name for name in self.comp[key]):
                    return False
            elif key == "base" and self.comp[key] not in item.base:
                return False
            elif key == "ilvl" and self.comp[key] > item.ilvl:
                return False
            elif key == "corrupted" and self.comp[key] != item.corrupted:
                return False
            elif key == "crafted" and self.comp[key] != item.crafted:
                return False
            elif key == "sockets" and self.comp[key] > item.sockets:
                return False
            elif key == "links" and self.comp[key] > item.links:
                return False
            elif key == "stacksize" and self.comp[key] > item.stacksize:
                return False
            elif key == "modcount_min" and self.comp[key] > item.modcount:
                return False
            elif key == "modcount_max" and self.comp[key] < item.modcount:
                return False
            elif key == "buyout" and self.comp[key] != item.buyout:
                return False
            elif key == "implicit":
                if not CompiledFilter._checkmods(self.comp[key]['mods'], item.implicit, self.comp[key]['match_min'], self.comp[key]['match_max']):
                    return False
            elif key == "explicit":
                if not CompiledFilter._checkmods(self.comp[key]['mods'], item.explicit, self.comp[key]['match_min'], self.comp[key]['match_max']):
                    return False
            elif key == "mods":
                if not CompiledFilter._checkmods(self.comp[key]['mods'], item.mods, self.comp[key]['match_min'], self.comp[key]['match_max']):
                    return False

        return True

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
                if CompiledFilter._checkexpr(expr, vals, mod):
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

class Filter:

    FILTER_INVALID_PRICE = "Invalid price '{}' in filter {}"
    FILTER_INVALID_PRICE_BASE = "Invalid price in filter: {}. Expected filter ot have a base"
    FILTER_INVALID_REGEX = "Invalid regex: '{}' in filter {}. Error while compiling: {}"

    _FILTER_PRICE_REGEX = re.compile('\s*([+\-*/]?)\s*(.+)')
    _NUMBER_REGEX = re.compile('[0-9]+(?:\.[0-9]+)?$')

    def __init__(self, title, criteria, enabled, category, id='', base_id=''):
        self.title = title
        self.criteria = criteria
        self.enabled = enabled
        self.category = category

        self.id = id
        self.baseId = base_id

    def validate(self):
        if self.criteria:
            if not self.baseId and 'price' in self.criteria:
                if not Filter.isPriceValid(self.criteria['price']):
                    raise AppException(Filter.FILTER_INVALID_PRICE.format(self.criteria['price'], self.title))

                # check if opr relies on base
                opr = Filter._FILTER_PRICE_REGEX.match(str(self.criteria['price'])).group(1)
                if opr != '':
                    raise AppException(Filter.FILTER_INVALID_PRICE_BASE.format(self.criteria['price']))

            try:
                for mod_key in ("implicit", "explicit", "mods"):
                    if mod_key in self.criteria:
                        for mod_filter in self.criteria[mod_key]['mods']:
                            re.compile(mod_filter['expr'])
            except re.error as e:
                raise AppException(Filter.FILTER_INVALID_REGEX.format(e.pattern, self.title, e))

    def compile(self, base={}):
        crit = self.criteria

        comp = dict(base)

        for key in crit:
            if key == 'type':
                types = []
                for itype in crit['type']:
                    for id in _ITEM_TYPE:
                        if itype == _ITEM_TYPE[id]:
                            types.append(id)
                            break
                comp['type'] = types
            elif key == 'name':
                comp['name'] = [name.lower() for name in crit[key]]

            elif key == 'price':
                comp[key] = Filter.compilePrice(crit[key], comp.get(key, None))

            elif key in ("implicit", "explicit", "mods"):
                mods = copy.deepcopy(crit[key])

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
                comp[key] = mods
            else:
                comp[key] = crit[key]

        return comp

    def toDict(self):
        return {
                'title': self.title,
                'enabled': self.enabled,
                'category': self.category,
                'id': self.id,
                'baseId': self.baseId,
                'criteria': self.criteria}

    @classmethod
    def fromDict(cls, data):
        return cls(
            data.get('title', data.get('id', '')),
            data.get('criteria', {}),
            data.get('enabled', True),
            data.get('category', 'user'),
            data.get('id', ''),
            data.get('baseid', ''))

    @staticmethod
    def isPriceValid(fltr_price):
        match = Filter._FILTER_PRICE_REGEX.match(str(fltr_price))
        if match is not None:
            opr, price = match.groups()
            if opr in ('*', '/'):
                return Filter._NUMBER_REGEX.match(price) is not None and float(price) > 0
            else:
                return cm.isPriceValid(price)
        return False

    @staticmethod
    def compilePrice(fltr_price, base_price=None):
        opr, price = Filter._FILTER_PRICE_REGEX.match(str(fltr_price)).groups()
        new_price = 0

        if opr != '' and base_price is None:
            raise AppException('Failed to compile price: {}. Missing base price.'.format(fltr_price))

        # factor
        if opr in ('', '+', '-'):
            amount, short = cm.priceFromString(price)
            val = cm.convert(float(amount), short)
        else:
            val = float(price)

        if opr == '':
            new_price = val
        elif opr == '+':
            new_price = base_price + val
        elif opr == '-':
            new_price = base_price - val
        elif opr == '*':
            new_price = base_price * val
        elif opr == '/':
            new_price = base_price / val

        return new_price


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

def get_item_links_string(item):
    links = ''
    lg = '-1'
    for socket in item.get('sockets', []):
        if lg != '-1':
            links += '-' if lg == socket['group'] else ' '
        links += socket['attr']
        lg = socket['group']

    return links


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
        return "{} {}".format(amount, cm.toWhisper(currency))

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


def parse_stashes_parallel(data, filters, stateMgr, resultHandler, numCores):
    item_count = 0

    league_stashes = []
    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == config.league:
            item_count += len(stash["items"])
            league_stashes.append(stash)

    results = Parallel(n_jobs=numCores)(delayed(parse_stash)(stash, filters) for stash in league_stashes)

    for item, stash, fltr in chain.from_iterable(results):
        if stateMgr.addItem(item["id"], get_item_price_raw(item, stash), stash["accountName"]):
            resultHandler(item, stash, fltr)

    parse_next_id(data, stateMgr)
    return len(data["stashes"]), len(league_stashes), item_count

def parse_stash(stash, filters):

    results = []
    for item in stash["items"]:
        curItem = Item(item, stash)
        for fltr in filters:
            if fltr.checkItem(curItem):
                results.append((item, stash, fltr))
                break
    return results

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
    __slots__ = tuple([x for x in _FILTER_PRIO.keys() if 'modcount' not in x] + ['modcount'])

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

        self.name = get_item_name(item).lower()
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

class PropValueType(IntEnum):
    WhiteOrPhysical = 0
    BlueOrModified = 1
    Fire = 4
    Cold = 5
    Lightning = 6
    Chaos = 7

class PropDisplayMode(IntEnum):
    Normal = 0
    StatReq = 1
    Progress = 2
    Format = 3

class ItemType(IntEnum):
    Normal = 0
    Magic = 1
    Rare = 2
    Unique = 3
    Gem = 4
    Currency = 5
    DivinationCard = 6
    QuestItem = 7
    Prophecy = 8
    Relic = 9

class ItemInfo:

    def __init__(self, item, stash):

        self.icon = item['icon']
        self.name = get_item_name(item)
        self.type = item['frameType']
        self.corrupted = item['corrupted']
        self.duplicated = item.get('duplicated', False)
        self.ilvl = item['ilvl']
        self.w = item['w']
        self.h = item['h']

        self.enchant = item.get('enchantMods', [])
        self.implicit = item.get('implicitMods', [])  #item.get('utilityMods', []))
        self.utility = item.get('utilityMods', [])
        self.explicit = item.get('explicitMods', [])
        self.crafted = item.get('craftedMods', [])

        self.sockets = get_item_sockets(item)
        self.links = get_item_links(item)
        self.links_string = get_item_links_string(item)
        self.identified = item['identified']

        # {req['name']: req['values'][0] if req['values'] else [] for req in item.get('requirements', [])}
        self.requirements = item.get('requirements', [])
        # {prop['name']: prop['values'][0] if prop['values'] else [] for prop in item.get('properties', [])}
        self.properties = item.get('properties', []) + item.get('additionalProperties', [])

        self.note = item.get('note')
        self.price = get_item_price_raw(item, stash)  #tmp





