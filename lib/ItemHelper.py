import copy
import itertools
import json
import re
from array import array
from enum import IntEnum
from itertools import chain
from json import JSONEncoder
from urllib.parse import urljoin

from joblib import Parallel, delayed

from lib.CurrencyManager import cm
from lib.Utility import AppException, isAbsoluteUrl

_FILTER_PRIO = {
    "base": 1,
    "price": 1,
    "ilvl": 1,
    "corrupted": 1,
    "unmodifiable": 1,
    "crafted": 1,
    "type": 1,
    "sockets": 1,
    "stacksize": 1,
    "modcount_min": 1,
    "modcount_max": 1,
    "buyout": 1,

    "level": 1,
    "level_max": 1,
    "exp": 1,
    "quality": 1,

    'fres': 6,
    'cres': 6,
    'lres': 6,
    'chres': 6,
    'ele_res': 6,
    'total_res': 6,

    'pdps': 3,
    'edps': 3,
    'dps': 3,

    'es': 3,
    'armour': 3,
    'evasion': 3,

    'total_life': 4,

    "links": 2,
    "name": 2,

    "implicit": 3,
    "explicit": 5,
    "mods": 5,
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

float_expr = '[0-9]+|[0-9]+\s*\.\s*[0-9]+'
_BO_PRICE_REGEX = re.compile('.*~(?:b/o|price)({num})(?:[/\\\\]({num}))?([a-z\-]+)'.format(num=float_expr))

# _BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")

expr_level = re.compile('([0-9]+).*')
phys_expr = re.compile('([0-9]+)% increased physical damage')
es_expr = re.compile('([0-9]+)% increased (?!maximum).*energy shield$')
armour_expr = re.compile('([0-9]+)% increased armour(?! during).*$')
evasion_expr = re.compile('([0-9]+)% increased .*evasion(?! rating).*$')

life_expr = re.compile('([\-+][0-9]+) to maximum life$')
strength_expr = re.compile('([\-+][0-9]+) to strength')
att_expr = re.compile('([\-+][0-9]+) to all attributes$')
str_mods = [strength_expr, att_expr]

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
            if key == "type":
                if item.type not in self.comp[key]:
                    return False
            elif key == "price":
                if item.price is not None and item.price > self.comp[key]:
                        return False
            elif key == "name":
                if not any(name in item.name for name in self.comp[key]):
                    return False
            elif key == "base":
                if self.comp[key] not in item.base:
                    return False
            elif key == "ilvl":
                if self.comp[key] > item.ilvl:
                    return False
            elif key == "corrupted":
                if self.comp[key] != item.corrupted:
                    return False
            elif key == "unmodifiable":
                if self.comp[key] != (item.corrupted or item.mirrored):
                    return False
            elif key == "crafted":
                if self.comp[key] != item.crafted:
                    return False
            elif key == "sockets":
                if self.comp[key] > item.sockets:
                    return False
            elif key == "links":
                if self.comp[key] > item.links:
                    return False
            elif key == "stacksize":
                if self.comp[key] > item.stacksize:
                    return False
            elif key == "modcount_min":
                if self.comp[key] > item.modcount:
                    return False
            elif key == "modcount_max":
                if self.comp[key] < item.modcount:
                    return False
            elif key == "buyout":
                if self.comp[key] != item.buyout:
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
            elif key == "level":
                if self.comp[key] > item.level:
                    return False
            elif key == "level_max":
                if self.comp[key] < item.level:
                    return False
            elif key == "exp":
                if self.comp[key] > item.exp:
                    return False
            elif key == "quality":
                if self.comp[key] > item.quality:
                    return False

            elif key == "es":
                if self.comp[key] > item.es:
                    return False
            elif key == "armour":
                if self.comp[key] > item.armour:
                    return False
            elif key == "evasion":
                if self.comp[key] > item.evasion:
                    return False
            elif key == "total_life":
                if self.comp[key] > item.total_life:
                    return False
            elif key == "fres":
                if self.comp[key] > item.fres:
                    return False
            elif key == "cres":
                if self.comp[key] > item.cres:
                    return False
            elif key == "lres":
                if self.comp[key] > item.lres:
                    return False
            elif key == "chres":
                if self.comp[key] > item.chres:
                    return False
            elif key == "ele_res":
                if self.comp[key] > item.ele_res:
                    return False
            elif key == "total_res":
                if self.comp[key] > item.total_res:
                    return False

            elif key == "edps":
                if self.comp[key] > item.edps:
                    return False
            elif key == "pdps":
                if self.comp[key] > item.pdps:
                    return False
            elif key == "dps":
                if self.comp[key] > item.dps:
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
            raise CompileException('Price is relative but base price is missing.'.format(fltr_price))

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


# used to propogate reasons for compilation failure
class CompileException(Exception):
    pass

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


# def get_item_buyout(item, stash):
#     price = get_item_price_raw(item, stash)
#     if price is not None:
#         match = _BO_PRICE_REGEX.match(price.lower())
#
#         if match is not None:
#             return float(match.group(2)) > 0
#     return False


def get_item_stacksize(item):
    return item.get("stackSize", 1)


def get_item_modcount(item):
    return len(item.get('explicitMods', [])) + len(item.get('implicitMods', [])) + len(item.get('craftedMods', []))


# def get_item_price_raw_old(item, stash):
#     price = None
#     if "note" in item:
#         price = item["note"]
#     elif stash["stash"].startswith("~b/o ") or stash["stash"].startswith("~price "):
#     #elif PRICE_REGEX.match(stash["stash"]):
#         price = stash["stash"]
#
#     return price

# def get_item_price_old(item, stash):
#     # Returns tuple (amount, currency)
#
#     price = get_item_price_raw(item, stash)
#     if price is not None:
#         match = _BO_PRICE_REGEX.match(price.lower())
#
#         if match is not None:
#             return match.group(2, 3)
#
#     return None

def get_item_price_raw(item, stash):
    match = None
    if 'note' in item:
        if _BO_PRICE_REGEX.match(item['note'].lower().replace(' ', '')):
            return item['note']

    if _BO_PRICE_REGEX.match(stash['stash'].lower().replace(' ', '')):
        return stash['stash']

    return None

def get_item_price(item, stash):
    match = None
    if 'note' in item:
        match = _BO_PRICE_REGEX.match(item['note'].lower().replace(' ', ''))

    if not match:
        match = _BO_PRICE_REGEX.match(stash['stash'].lower().replace(' ', ''))

    if match:
        num, denom, curr = match.groups()
        denom = 1 if denom is None or float(denom) == 0 else float(denom)
        return float(num) / denom, curr
    return None

def get_item_price_whisper(item, stash):
    # Returns format of {amount} {currency}

    price = get_item_price(item, stash)
    if price is not None:
        amount, currency = price
        return int(amount) if int(amount) == amount else amount, cm.toWhisper(currency)

    return None

def get_item_price_display(item, stash):
    # Returns format of {amount} {currency}

    price = get_item_price(item, stash)
    if price is not None:
        amount, currency = price
        return int(amount) if int(amount) == amount else round(amount, 2), cm.toFull(currency)

    return None

def get_whisper_msg(item, stash):
    template = "@{} Hi, I would like to buy your {}{} listed{} in {} (stash tab \"{}\"; position: left {}, top {})"

    price = get_item_price_whisper(item, stash)
    price_str = " for {} {}".format(*price) if price is not None else ""

    size = get_item_stacksize(item)
    stack_size_str = "" if size == 1 else str(size) + " "

    return template.format(stash["lastCharacterName"], stack_size_str, get_item_name(item),
                           price_str, item["league"], stash["stash"],
                           item["x"] + 1, item["y"] + 1)


# def get_item_info(item, stash):
#     template = "{}{}: ilvl: {}, Links: {}, Implicit: {}, Explicit: {}, Price: {}, Stack: {}, Account: {}, " \
#                "Sockets: {}"
#
#     price = get_item_price_raw(item, stash)
#     if price is None:
#         price = "n/a"
#
#     return template.format("!!! CORRUPTED !!! " if item["corrupted"] else "",
#                            get_item_name(item), item["ilvl"],
#                            get_item_links(item), item.get("implicitMods", []), item.get("explicitMods", []),
#                            price, get_item_stacksize(item), stash["accountName"], get_item_sockets(item))

def get_prop_value(item, name):
    for prop in itertools.chain(item.get('properties', []), item.get('additionalProperties', [])):
        if prop['name'] == name:
            return prop['values']  # get?
    return None

def get_item_prop(item, name):
    for prop in itertools.chain(item.get('properties', []), item.get('additionalProperties', [])):
        if prop['name'] == name:
            return prop  # get?
    return None

def parse_stashes(data, filters, league, stateMgr, resultHandler):
    league_tabs = 0
    item_count = 0

    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
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


def parse_stashes_parallel(data, filters, league, stateMgr, resultHandler, numCores):
    item_count = 0

    league_stashes = []
    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
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


def get_item_pdps(quality, unmodifiable, mods, pavg, aps):
    if unmodifiable or quality == 20:
        return pavg*aps

    total = 0
    for mod in mods:
        match = phys_expr.match(mod)
        if match:
            total += float(match.group(1))
    return pavg * (120 + total) / (quality + 100 + total) * aps

def get_item_es(quality, unmodifiable, mods, es):
    if unmodifiable or quality == 20:
        return es

    total = 0
    for mod in mods:
        match = es_expr.match(mod)
        if match:
            total += float(match.group(1))
    return es * (120 + total) / (quality + 100 + total)

def get_item_armour(quality, unmodifiable, mods, armour):
    if unmodifiable or quality == 20:
        return armour

    total = 0
    for mod in mods:
        match = armour_expr.match(mod)
        if match:
            total += float(match.group(1))
    return armour * (120 + total) / (quality + 100 + total)

def get_item_evasion(quality, unmodifiable, mods, evasion):
    if unmodifiable or quality == 20:
        return evasion

    total = 0
    for mod in mods:
        match = armour_expr.match(mod)
        if match:
            total += float(match.group(1))
    return evasion * (120 + total) / (quality + 100 + total)


def get_item_life(mods):
    life = 0
    for mod in mods:
        match = life_expr.match(mod)
        if match:
            life += float(match.group(1))

    return life + get_item_strength(mods) / 2


def get_item_strength(mods):
    str = 0
    for mod in mods:
        for expr in str_mods:
            match = expr.match(mod)
            if match:
                str += float(match.group(1))
                break

    return str


class Item:
    # __slots__ = tuple([x for x in _FILTER_PRIO.keys() if 'modcount' not in x] + ['modcount'])
    __slots__ = ('_item', 'name', 'base', 'ilvl', 'links', 'corrupted', 'mirrored', 'stacksize', 'price',
                 '_implicit', '_explicit', '_mods', 'sockets', 'buyout', 'type', 'crafted', 'modcount',
                 'quality', '_armour', '_evasion', '_es', '_total_life', 'level', 'exp',
                 '_fres', '_cres', '_lres', '_chres', '_ele_res', '_total_res',
                 '_dps', '_pdps', '_edps')

    res_mods = {
        re.compile('((?:\+|-)[0-9]+)% to fire and cold resistances$'): ('_fres', '_cres'),
        re.compile('((?:\+|-)[0-9]+)% to fire and lightning resistances$'): ('_fres', '_lres'),
        re.compile('((?:\+|-)[0-9]+)% to cold and lightning resistances$'): ('_cres', '_lres'),
        re.compile('((?:\+|-)[0-9]+)% to fire resistance$'): ('_fres',),
        re.compile('((?:\+|-)[0-9]+)% to cold resistance$'): ('_cres',),
        re.compile('((?:\+|-)[0-9]+)% to lightning resistance$'): ('_lres',),
        re.compile('((?:\+|-)[0-9]+)% to chaos resistance$'): ('_chres',),
        re.compile('((?:\+|-)[0-9]+)% to all elemental resistances$'): ('_fres', '_cres', '_lres')
    }

    def __init__(self, item, stash):
        self._item = item
        self.links = get_item_links(item)
        self.sockets = get_item_sockets(item)
        self.corrupted = item['corrupted']
        self.mirrored = item.get('duplicated', False)
        self.ilvl = item['ilvl']
        self.base = item['typeLine'].lower()
        self.crafted = 'craftedMods' in item
        # self.type = _ITEM_TYPE[item['frameType']]
        self.type = item['frameType']
        self.stacksize = get_item_stacksize(item)
        self.modcount = get_item_modcount(item)

        self.name = get_item_name(item).lower()
        price = get_item_price(item, stash)

        self.price = cm.convert(*price) if price is not None else None
        self.buyout = self.price is not None and self.price > 0

        self._implicit = None
        self._explicit = None
        self._mods = None

        # # Properties and computed fields
        # unmodifiable = self.corrupted or self.mirrored

        lvl, exp = get_prop_value(item, 'Level'), get_item_prop(item, 'Experience')

        self.level = float(lvl[0][0].split()[0]) if lvl else 0
        self.exp = exp['progress'] * 100 if exp else 0

        quality = get_prop_value(item, 'Quality')
        self.quality = int(quality[0][0].strip('+%')) if quality else 0

        self._es = None
        self._armour = None
        self._evasion = None
        self._total_life = None

        self._fres = None
        self._cres = None
        self._lres = None
        self._chres = None
        self._ele_res = None
        self._total_res = None

        self._edps = None
        self._pdps = None
        self._dps = None

    @property
    def implicit(self):
        if self._implicit is None:
            self._implicit = [mod.lower() for mod in self._item.get('implicitMods', [])]
        return self._implicit

    @property
    def explicit(self):
        if self._explicit is None:
            self._explicit = [mod.lower() for mod in self._item.get('explicitMods', [])]
        return self._explicit

    @property
    def mods(self):
        if self._mods is None:
            self._mods = itertools.chain(self.implicit, self.explicit, [mod.lower() for mod in
                                                                        itertools.chain(self._item.get('enchantMods', []),
                                                                                        self._item.get('craftedMods', []))])
        return self._mods

    @property
    def es(self):
        if self._es is None:
            val = get_prop_value(self._item, 'Energy Shield')
            self._es = get_item_es(self.quality, self.corrupted or self.mirrored,
                                   self.mods, float(val[0][0])) if val else 0
        return self._es

    @property
    def armour(self):
        if self._armour is None:
            armour = get_prop_value(self._item, 'Armour')
            self._armour = get_item_armour(self.quality, self.corrupted or self.mirrored,
                                           self.mods, float(armour[0][0])) if armour else 0
        return self._armour

    @property
    def evasion(self):
        if self._evasion is None:
            val = get_prop_value(self._item, 'Evasion')
            self._evasion = get_item_evasion(self.quality, self.corrupted or self.mirrored,
                                             self.mods, float(val[0][0])) if val else 0
        return self._evasion

    @property
    def total_life(self):
        if self._total_life is None:
            self._total_life = get_item_life(self.mods)
        return self._total_life

    @property
    def edps(self):
        if self._edps is None:
            self._fill_dps()
        return self._edps

    @property
    def pdps(self):
        if self._pdps is None:
            self._fill_dps()
        return self._pdps

    @property
    def dps(self):
        if self._dps is None:
            self._fill_dps()
        return self._dps

    def _fill_dps(self):
        aps = get_prop_value(self._item, 'Attacks per Second')
        if aps:
            aps = float(aps[0][0])

            pavg, eavg, cavg = get_prop_value(self._item, 'Physical Damage'), \
                               get_prop_value(self._item, 'Elemental Damage'), get_prop_value(self._item, 'Chaos Damage')

            if pavg:
                pavg = sum((float(i) for i in pavg[0][0].split('-'))) / 2
                self._pdps = get_item_pdps(self.quality, self.corrupted or self.mirrored, self.mods, pavg, aps)
            else:
                self._pdps = 0

            self._edps = sum((float(i) for i in eavg[0][0].split('-'))) / 2 * aps if eavg else 0
            cavg = sum((float(i) for i in cavg[0][0].split('-')))/2 if cavg else 0

            self._dps = self._pdps + self._edps + cavg * aps
        else:
            self._dps = 0
            self._pdps = 0
            self._edps = 0

    @property
    def fres(self):
        if self._fres is None:
            self._fill_res()
        return self._fres

    @property
    def cres(self):
        if self._cres is None:
            self._fill_res()
        return self._cres

    @property
    def lres(self):
        if self._lres is None:
            self._fill_res()
        return self._lres

    @property
    def chres(self):
        if self._chres is None:
            self._fill_res()
        return self._chres

    @property
    def ele_res(self):
        if self._ele_res is None:
            self._fill_res()
        return self._ele_res

    @property
    def total_res(self):
        if self._total_res is None:
            self._fill_res()
        return self._total_res

    def _fill_res(self):
        self._cres = 0
        self._fres = 0
        self._lres = 0
        self._chres = 0

        for mod in self.mods:
            for expr in self.res_mods:
                match = expr.match(mod)
                if match:
                    val = float(match.group(1))
                    for res in self.res_mods[expr]:
                        self.__setattr__(res, self.__getattribute__(res) + val)
                    break

        self._ele_res = self._fres + self._cres + self._lres
        self._total_res = self._ele_res + self._chres


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

    def __init__(self, item, stash, baseUrl):

        self.icon = item['icon']
        if not isAbsoluteUrl(self.icon):
            self.icon = urljoin(baseUrl, self.icon)

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
        self.price = get_item_price_display(item, stash)





