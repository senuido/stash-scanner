import copy
import itertools
import re
from enum import IntEnum, Enum
from itertools import chain
from urllib.parse import urljoin

from joblib import Parallel, delayed

from lib.CurrencyManager import cm
from lib.Utility import isAbsoluteUrl
from array import array

float_expr = '[0-9]+|[0-9]+\s*\.\s*[0-9]+'
_BO_PRICE_REGEX = re.compile('.*~(?:b/o|price)({num})(?:[/\\\\]({num}))?([a-z\-]+)'.format(num=float_expr))

# _BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")

expr_level = re.compile('([0-9]+).*')
phys_expr = re.compile('([0-9]+)% increased Physical Damage$')
es_expr = re.compile('([0-9]+)% increased (?!maximum).*Energy Shield$')
armour_expr = re.compile('([0-9]+)% increased Armour(?! during).*$')
evasion_expr = re.compile('([0-9]+)% increased .*Evasion(?! Rating).*$')

life_expr = re.compile('([\-+][0-9]+) to maximum Life$')
strength_expr = re.compile('([\-+][0-9]+) to Strength')
dex_expr = re.compile('([\-+][0-9]+) to .*Dexterity$')
int_expr = re.compile('([\-+][0-9]+) to .*Intelligence$')
attributes_expr = re.compile('([\-+][0-9]+) to all Attributes$')
str_mods = [strength_expr, attributes_expr]

cold_res_expr = re.compile('([\-+][0-9]+)% to(?: Fire and)? Cold(?: and Lightning)? Resistances?$')
fire_res_expr = re.compile('([\-+][0-9]+)% to Fire(?: and (?:Cold|Lightning))? Resistances?$')
lightning_res_expr = re.compile('([\-+][0-9]+)% to(?: (?:Cold|Fire) and)? Lightning Resistances?$')
chaos_res_expr = re.compile('([\-+][0-9]+)% to Chaos Resistance$')
ele_res_expr = re.compile('([\-+][0-9]+)% to all Elemental Resistances$')


class StashTab:
    def __init__(self, stash):
        self.name = stash['stash']
        self.items = stash['items']
        self.public = stash['public']
        self.account_name = stash['accountName']
        self.last_char_name = stash['lastCharacterName']
        self.league = self.items[0]['league'] if self.items else None

        self.price = get_price(self.name)

    def get_stash_price_raw(self):
        if self.price is not None:
            return self.name
        return None

def get_stash_price(stash):
    return get_price(stash['stash'])

def get_price(price):
    match = _BO_PRICE_REGEX.match(price.lower().replace(' ', ''))

    if match:
        num, denom, curr = match.groups()
        denom = 1 if denom is None or float(denom) == 0 else float(denom)
        return float(num) / denom, curr
    return None

def get_stash_price_raw(stash):
    if get_stash_price(stash):
        return stash['stash']
    return None

# res_mods = {
#         re.compile('([\-+][0-9]+)% to Fire and Cold Resistances$'): ('_fres', '_cres'),
#         re.compile('([\-+][0-9]+)% to Fire and Lightning Resistances$'): ('_fres', '_lres'),
#         re.compile('([\-+][0-9]+)% to Cold and Lightning Resistances$'): ('_cres', '_lres'),
#         re.compile('([\-+][0-9]+)% to Fire Resistance$'): ('_fres',),
#         re.compile('([\-+][0-9]+)% to Cold Resistance$'): ('_cres',),
#         re.compile('([\-+][0-9]+)% to Lightning Resistance$'): ('_lres',),
#         re.compile('([\-+][0-9]+)% to Chaos Resistance$'): ('_chres',),
#         re.compile('([\-+][0-9]+)% to all Elemental Resistances$'): ('_fres', '_cres', '_lres')
#     }

# def get_item_buyout(item, stash):
#     price = get_item_price_raw(item, stash)
#     if price is not None:
#         match = _BO_PRICE_REGEX.match(price.lower())
#
#         if match is not None:
#             return float(match.group(2)) > 0
#     return False

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





# def parse_stashes(data, filters, league, stateMgr, resultHandler):
#     league_tabs = 0
#     item_count = 0
#
#     for stash in data["stashes"]:
#         if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
#             league_tabs += 1
#             item_count += len(stash["items"])
#             for item in stash["items"]:
#                 curItem = Item(item, stash)
#                 for fltr in filters:
#                     if fltr.checkItem(curItem):
#                         if stateMgr.addItem(curItem.id, get_item_price_raw(item, stash), stash["accountName"]):
#                             resultHandler(curItem, stash, fltr)
#                         break
#
#     parse_next_id(data, stateMgr)
#     return len(data["stashes"]), league_tabs, item_count


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

        if stateMgr.addItem(item.id, item.get_price_raw(get_stash_price_raw(stash)), stash["accountName"]):
            resultHandler(copy.deepcopy(item), copy.copy(stash), copy.deepcopy(fltr))

    parse_next_id(data, stateMgr)
    return len(data["stashes"]), len(league_stashes), item_count


def parse_stash(stash, filters):

    results = []
    stash_price = get_stash_price(stash)
    for item in stash["items"]:
        curItem = Item(item, stash_price)
        for fltr in filters:
            if fltr.checkItem(curItem):
                results.append((curItem, stash, fltr))
                break
    return results

# def lower_json(x):
#     if isinstance(x, list):
#         return [lower_json(v) for v in x]
#     if isinstance(x, dict):
#         d = {}
#         for k, v in x.items():
#             if k.lower() in ("title"):
#                 d[k.lower()] = v
#             else:
#                 d[k.lower()] = lower_json(v)
#         return d
#         # return {k.lower(): lower_keys(v) for k, v in x.items()}
#     if isinstance(x, str):
#         return x.lower()
#     return x

# def get_item_life(mods):
#     life = 0
#     for mod in mods:
#         match = life_expr.match(mod)
#         if match:
#             life += float(match.group(1))
#
#     return life + get_item_strength(mods) / 2
#
#
# def get_item_strength(mods):
#     str = 0
#     for mod in mods:
#         for expr in str_mods:
#             match = expr.match(mod)
#             if match:
#                 str += float(match.group(1))
#                 break
#
#     return str


class Item:
    __slots__ = ('_item', 'c_name', 'base', 'ilvl', 'links_count', 'corrupted', 'mirrored', 'identified', 'stacksize',
                 'c_price',
                 'implicit', 'explicit', 'enchant', 'craft', '_mods', 'sockets_count', 'buyout', 'type',
                 'crafted', 'enchanted', 'modcount', 'quality', 'level', 'exp',

                 'price',  # price before conversion

                 '_armour', '_evasion', '_es', '_life',
                 '_fres', '_cres', '_lres', '_chres', '_ele_res',
                 '_aps', '_dps', '_pdps', '_edps', '_formatted_properties',
                 '_strength_bonus', '_dex_bonus', '_int_bonus', '_attributes_bonus')

    def __init__(self, item, stash_price):
        self._item = item

        self.links_count = self._get_item_links_count()
        self.sockets_count = len(self.sockets)
        self.ilvl = item['ilvl']
        self.base = item['typeLine'].lower()
        self.corrupted = item['corrupted']
        self.mirrored = item.get('duplicated', False)
        self.identified = item['identified']

        # self.type = _ITEM_TYPE[item['frameType']]
        self.type = item['frameType']
        self.stacksize = item.get("stackSize", 1)
        self.c_name = self.name.lower()

        self.price = self.get_price(stash_price)
        self.c_price = cm.convert(*self.price) if self.price is not None else None
        self.buyout = self.c_price is not None and self.c_price > 0

        self.implicit = self._item.get('implicitMods', [])
        self.explicit = self._item.get('explicitMods', [])
        self.enchant = self._item.get('enchantMods', [])
        self.craft = self._item.get('craftedMods', [])
        self._mods = None

        self.crafted = len(self.craft) > 0
        self.enchanted = len(self.enchant) > 0
        self.modcount = len(self.implicit) + len(self.explicit) + len(self.enchant) + len(self.craft)

        # # Properties and computed fields

        lvl, exp = self.get_prop_value('Level'), self.get_item_prop('Experience')

        self.level = float(lvl[0][0].split()[0]) if lvl else 0
        self.exp = exp['progress'] * 100 if exp else 0

        quality = self.get_prop_value('Quality')
        self.quality = int(quality[0][0].strip('+%')) if quality else 0

        self._es = None
        self._armour = None
        self._evasion = None

        self._aps = None
        self._edps = None
        self._pdps = None
        self._dps = None

        self._attributes_bonus = None
        self._strength_bonus = None
        self._dex_bonus = None
        self._int_bonus = None
        self._life = None

        self._fres = None
        self._cres = None
        self._lres = None
        self._chres = None
        self._ele_res = None

        self._formatted_properties = None

    @property
    def mods(self):
        if self._mods is None:
            self._mods = list(itertools.chain(self.explicit, self.implicit, self.enchant, self.craft))
        return self._mods

    @property
    def es(self):
        if self._es is None:
            val = self.get_prop_value('Energy Shield')
            self._es = self.get_item_es(self.quality, self.corrupted or self.mirrored,
                                   self.mods, float(val[0][0])) if val else 0
        return self._es

    @property
    def armour(self):
        if self._armour is None:
            armour = self.get_prop_value('Armour')
            self._armour = self.get_item_armour(self.quality, self.corrupted or self.mirrored,
                                           self.mods, float(armour[0][0])) if armour else 0
        return self._armour

    @property
    def evasion(self):
        if self._evasion is None:
            val = self.get_prop_value('Evasion')
            self._evasion = self.get_item_evasion(self.quality, self.corrupted or self.mirrored,
                                             self.mods, float(val[0][0])) if val else 0
        return self._evasion

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

    @property
    def aps(self):
        if self._aps is None:
            aps = self.get_prop_value('Attacks per Second')
            self._aps = float(aps[0][0]) if aps else 0
        return self._aps

    def _fill_dps(self):
        if self.aps:
            pavg, eavg, cavg = self.get_prop_value('Physical Damage'), \
                               self.get_prop_value('Elemental Damage'), self.get_prop_value('Chaos Damage')

            if pavg:
                pavg = sum((float(i) for i in pavg[0][0].split('-'))) / 2
                self._pdps = self.get_item_pdps(self.quality, self.corrupted or self.mirrored, self.mods, pavg, self.aps)
            else:
                self._pdps = 0

            self._edps = sum((float(i) for i in eavg[0][0].split('-'))) / 2 * self.aps if eavg else 0
            cavg = sum((float(i) for i in cavg[0][0].split('-')))/2 if cavg else 0

            self._dps = self._pdps + self._edps + cavg * self.aps
        else:
            self._dps = 0
            self._pdps = 0
            self._edps = 0

    @property
    def fres(self):
        if self._fres is None:
            self._fres = Item.get_mod_total(fire_res_expr, self.mods)
        return self._fres

    @property
    def cres(self):
        if self._cres is None:
            self._cres = Item.get_mod_total(cold_res_expr, self.mods)
        return self._cres

    @property
    def lres(self):
        if self._lres is None:
            self._lres = Item.get_mod_total(lightning_res_expr, self.mods)
        return self._lres

    @property
    def chres(self):
        if self._chres is None:
            self._chres = Item.get_mod_total(chaos_res_expr, self.mods)
        return self._chres

    @property
    def ele_res(self):
        if self._ele_res is None:
            self._ele_res = Item.get_mod_total(ele_res_expr, self.mods)
        return self._ele_res

    @property
    def strength_bonus(self):
        if self._strength_bonus is None:
            self._strength_bonus = Item.get_mod_total(strength_expr, self.mods)
        return self._strength_bonus

    @property
    def dex_bonus(self):
        if self._dex_bonus is None:
            self._dex_bonus = Item.get_mod_total(dex_expr, self.mods)
        return self._dex_bonus

    @property
    def int_bonus(self):
        if self._int_bonus is None:
            self._int_bonus = Item.get_mod_total(int_expr, self.mods)
        return self._int_bonus

    @property
    def attributes_bonus(self):
        if self._attributes_bonus is None:
            self._attributes_bonus = Item.get_mod_total(attributes_expr, self.mods)
        return self._attributes_bonus

    @property
    def life(self):
        if self._life is None:
            self._life = Item.get_mod_total(life_expr, self.mods)
        return self._life

    @property
    def formatted_properties(self):
        if self._formatted_properties is None:
            self._formatted_properties = \
                [ItemProperty.format_property(prop['name'], prop['values'])
                 for prop in self.properties
                 if prop['displayMode'] == PropDisplayMode.Format]
        return self._formatted_properties

    @property
    def prophecy(self):
        return self._item.get('prophecyText', '')

    @property
    def w(self):
        return self._item['w']

    @property
    def h(self):
        return self._item['h']

    @property
    def x(self):
        return self._item['x']

    @property
    def y(self):
        return self._item['y']

    @property
    def league(self):
        return self._item['league']

    @property
    def utility(self):
        return self._item.get('utilityMods', [])

    @property
    def icon(self):
        return self._item['icon']

    @property
    def requirements(self):
        return self._item.get('requirements', [])

    @property
    def properties(self):
        return self._item.get('properties', [])

    @property
    def additional_properties(self):
        return self._item.get('additionalProperties', [])

    @property
    def note(self):
        return self._item.get('note', '')

    @property
    def name(self):
        return _LOCALIZATION_REGEX.sub('', '{} {}'.format(self._item['name'], self._item['typeLine'])).strip()

    @property
    def sockets(self):
        return self._item['sockets']

    @property
    def id(self):
        return self._item['id']

    def _get_item_links_count(self):
        groups = array('I', [0]) * 6
        for socket in self.sockets:
            groups[socket['group']] += 1

        return max(groups)

    def get_item_prop(self, name):
        for prop in itertools.chain(self.properties, self.additional_properties):
            if prop['name'] == name:
                return prop
        return None

    def get_prop_value(self, name):
        prop = self.get_item_prop(name)
        if prop:
            return prop['values']
        return None

    # def get_property_value(self, name):
    #     vals = get_prop_value(self._item, name)
    #     if vals:
    #         vals = [val[0] for val in vals]
    #     return vals

    # def _fill_res(self):
    #     self._cres = 0
    #     self._fres = 0
    #     self._lres = 0
    #     self._chres = 0
    #
    #     for mod in self.mods:
    #         for expr in self.res_mods:
    #             match = expr.match(mod)
    #             if match:
    #                 val = float(match.group(1))
    #                 for res in self.res_mods[expr]:
    #                     self.__setattr__(res, self.__getattribute__(res) + val)
    #                 break
    #
    #     self._ele_res = self._fres + self._cres + self._lres
    #     self._total_res = self._ele_res + self._chres

    @staticmethod
    def get_mod_total(expr, mods, skip_vals=False):
        total = 0
        matched = False

        if not expr.groups:
            skip_vals = True

        for mod in mods:
            match = expr.match(mod)
            if match:
                if skip_vals:
                    return 1

                matched = True
                for val in match.groups():
                    total += float(val)
                    # return total / expr.groups

        if matched:
            return total / expr.groups
        return 0
        # return None maybe do this to allow differentiation between unmatched and a total of 0

    def get_item_links_string(self):
        links = ''
        link_group = None
        for socket in self.sockets:
            if link_group is not None:
                links += '-' if link_group == socket['group'] else ' '
            links += socket['attr']
            link_group = socket['group']

        return links

    @staticmethod
    def get_item_pdps(quality, unmodifiable, mods, pavg, aps):
        if unmodifiable or quality == 20:
            return pavg * aps

        total = 0
        for mod in mods:
            match = phys_expr.match(mod)
            if match:
                total += float(match.group(1))
        return pavg * (120 + total) / (quality + 100 + total) * aps

    @staticmethod
    def get_item_es(quality, unmodifiable, mods, es):
        if unmodifiable or quality == 20:
            return es

        total = 0
        for mod in mods:
            match = es_expr.match(mod)
            if match:
                total += float(match.group(1))
        return es * (120 + total) / (quality + 100 + total)

    @staticmethod
    def get_item_armour(quality, unmodifiable, mods, armour):
        if unmodifiable or quality == 20:
            return armour

        total = 0
        for mod in mods:
            match = armour_expr.match(mod)
            if match:
                total += float(match.group(1))
        return armour * (120 + total) / (quality + 100 + total)

    @staticmethod
    def get_item_evasion(quality, unmodifiable, mods, evasion):
        if unmodifiable or quality == 20:
            return evasion

        total = 0
        for mod in mods:
            match = armour_expr.match(mod)
            if match:
                total += float(match.group(1))
        return evasion * (120 + total) / (quality + 100 + total)

    def get_item_price_raw(self):
        if self.price is not None:
            return self.note
        return None

    def get_price(self, stash_price):
        price = get_price(self.note)
        return price if price is not None else stash_price

    def get_price_raw(self, stash_raw_price):
        raw_price = self.get_item_price_raw()
        if raw_price is not None:
            return raw_price
        return stash_raw_price

    # TODO MOVE?
    def get_item_price_whisper(self):
        # Returns format of {amount} {currency}

        price = self.price
        if price is not None:
            amount, currency = price
            return int(amount) if int(amount) == amount else amount, cm.toWhisper(currency)

        return None

    # TODO MOVE?
    def get_item_price_display(self):
        # Returns format of {amount} {currency}

        price = self.price
        if price is not None:
            amount, currency = price
            return int(amount) if int(amount) == amount else round(amount, 2), cm.toFull(currency)

        return None

    # TODO MOVE?
    def get_whisper_msg(self, stash):
        template = '@{} Hi, I would like to buy your {}{} listed{} in {} (stash tab \"{}\"; position: left {}, top {})'

        price = self.get_item_price_whisper()
        price_str = ' for {} {}'.format(*price) if price is not None else ''

        stack_size_str = '' if self.stacksize == 1 else str(self.stacksize) + ' '

        return template.format(stash['lastCharacterName'], stack_size_str, self.name,
                               price_str, self.league, stash['stash'],
                               self.x + 1, self.y + 1)

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

class ItemProperty:
    class PropertyValue:
        def __init__(self, val):
            self.val = val[0]
            # try:
            self.type = PropValueType(val[1])
            # except ValueError:
            #     self.type = PropValueType.WhiteOrPhysical

    def __init__(self, prop):
        self.values = [ItemProperty.PropertyValue(val) for val in prop.get('values', [])]

        # try:
        self.display_mode = PropDisplayMode(prop['displayMode'])
        # except ValueError:
        #     self.display_mode = PropDisplayMode.Normal

        self.name = prop['name']
        self.progress = prop.get('progress')

    def format(self):
        format_string = re.sub('%[0-9]+', '{}', self.name)
        return format_string.format(*[pv.val for pv in self.values])

    @staticmethod
    def format_property(name, values):
        format_string = re.sub('%[0-9]+', '{}', name)
        return format_string.format(*[val[0] for val in values])


class ItemSocketType(Enum):
    Strength = 'S'
    Dexterity = 'D'
    Intelligence = 'I'
    Generic = 'G'

class ItemSocket:
    def __init__(self, socket):
        self.type = ItemSocketType(socket['attr'])
        self.group = socket['group']