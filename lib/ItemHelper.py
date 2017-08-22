import itertools
import re
from enum import IntEnum, Enum

from array import array

from lib.CurrencyManager import cm
from lib.ItemCollection import ItemCollection
from lib.Utility import logger
from lib.ItemClass import ItemClass, dir_to_id

float_expr = '[0-9]+|[0-9]+\s*\.\s*[0-9]+'
_BO_PRICE_REGEX = re.compile('.*~(?:b/o|price)({num})(?:[/\\\\]({num}))?([a-z\-]+)'.format(num=float_expr))

# _BO_PRICE_REGEX = re.compile('.*~(b/o|price)\s+([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
_LOCALIZATION_REGEX = re.compile("<<.*>>")
superior_expr = re.compile('^Superior ')
dir_expr = re.compile(r'.*2DItems[/\\](.*)')

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


def get_price(price):
    match = _BO_PRICE_REGEX.match(price.lower().replace(' ', ''))

    if match:
        num, denom, curr = match.groups()
        denom = 1 if denom is None or float(denom) == 0 else float(denom)
        return float(num) / denom, curr
    return None


class Item:
    __slots__ = ('_item', 'c_name', 'c_base', 'ilvl', 'links_count', 'corrupted', 'mirrored', 'identified', 'stacksize',
                 'implicit', 'explicit', 'enchant', 'craft', '_mods', 'sockets_count', 'buyout', 'type',
                 'crafted', 'enchanted', 'modcount',
                 '_quality', '_level', '_exp',

                 'price',  # price before conversion
                 'c_price',
                 '_iclass', 'rarity',

                 '_armour', '_evasion', '_es', '_life',
                 '_fres', '_cres', '_lres', '_chres', '_ele_res',
                 '_aps', '_crit', '_block',
                 '_dps', '_pdps', '_edps',
                 '_formatted_properties',
                 '_strength_bonus', '_dex_bonus', '_int_bonus', '_attributes_bonus')

    def __init__(self, item, stash_price):
        self._item = item

        self.links_count = self._get_item_links_count()
        self.sockets_count = len(self.sockets)
        self.ilvl = item['ilvl']
        self.corrupted = item['corrupted']
        self.mirrored = item.get('duplicated', False)
        self.identified = item['identified']

        self.c_base = self.base.lower()
        self.c_name = '{} {}'.format(self._get_name().lower(), self.c_base).strip()

        # self.type = _ITEM_TYPE[item['frameType']]
        self.type = item['frameType']
        self.rarity = self.get_rarity()
        self.stacksize = item.get("stackSize", 1)

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

        # Properties and on-demand computed fields
        self._iclass = None
        self._quality = None
        self._level = None
        self._exp = None

        self._es = None
        self._armour = None
        self._evasion = None

        self._aps = None
        self._crit = None
        self._block = None

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
    def modifiable(self):
        return not (self.corrupted or self.mirrored)

    @property
    def iclass(self):
        if self._iclass is None:
            self._iclass = self.get_item_class()
        return self._iclass

    @property
    def quality(self):
        if self._quality is None:
            quality = self.get_prop_value('Quality')
            self._quality = int(quality[0][0].strip('+%')) if quality else 0
        return self._quality

    @property
    def level(self):
        if self._level is None:
            level = self.get_prop_value('Level')
            self._level = float(level[0][0].split()[0]) if level else 0
        return self._level

    # @property
    # def tier(self):
    #     if self._tier is None:
    #         tier = self.get_prop_value()

    @property
    def exp(self):
        if self._exp is None:
            exp = self.get_item_prop('Experience')
            self._exp = float(exp['progress']) * 100 if exp else 0
        return self._exp

    @property
    def es(self):
        if self._es is None:
            val = self.get_prop_value('Energy Shield')
            self._es = self.get_item_es(self.quality, self.modifiable,
                                   self.mods, float(val[0][0])) if val else 0
        return self._es

    @property
    def armour(self):
        if self._armour is None:
            armour = self.get_prop_value('Armour')
            self._armour = self.get_item_armour(self.quality, self.modifiable,
                                           self.mods, float(armour[0][0])) if armour else 0
        return self._armour

    @property
    def evasion(self):
        if self._evasion is None:
            val = self.get_prop_value('Evasion Rating')
            self._evasion = self.get_item_evasion(self.quality, self.modifiable,
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

    @property
    def crit(self):
        if self._crit is None:
            crit = self.get_prop_value('Critical Strike Chance')
            self._crit = float(crit[0][0].strip('%')) if crit else 0
        return self._crit

    @property
    def block(self):
        if self._block is None:
            block = self.get_prop_value('Chance to Block')
            self._block = float(block[0][0].strip('%')) if block else 0
        return self._block

    def _fill_dps(self):
        if self.aps:
            pavg, eavg, cavg = self.get_prop_value('Physical Damage'), \
                               self.get_prop_value('Elemental Damage'), self.get_prop_value('Chaos Damage')

            if pavg:
                pavg = sum((float(i) for i in pavg[0][0].split('-'))) / 2
                self._pdps = self.get_item_pdps(self.quality, self.modifiable, self.mods, pavg, self.aps)
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
    def base(self):
        return _LOCALIZATION_REGEX.sub('', self._item['typeLine'])

    @property
    def name(self):
        return '{} {}'.format(self._get_name(), self.base).strip()

    @property
    def sockets(self):
        return self._item['sockets']

    @property
    def id(self):
        return self._item['id']

    def _get_name(self):
        return _LOCALIZATION_REGEX.sub('', self._item['name'])

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

    def get_rarity(self):
        try:
            return ItemRarity(self.type)
        except ValueError:
            return ItemRarity.Normal



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
    def get_item_pdps(quality, modifiable, mods, pavg, aps):
        if not modifiable or quality == 20:
            return pavg * aps

        total = 0
        for mod in mods:
            match = phys_expr.match(mod)
            if match:
                total += float(match.group(1))
        return pavg * (120 + total) / (quality + 100 + total) * aps

    @staticmethod
    def get_item_es(quality, modifiable, mods, es):
        if not modifiable or quality == 20:
            return es

        total = 0
        for mod in mods:
            match = es_expr.match(mod)
            if match:
                total += float(match.group(1))
        return es * (120 + total) / (quality + 100 + total)

    @staticmethod
    def get_item_armour(quality, modifiable, mods, armour):
        if not modifiable or quality == 20:
            return armour

        total = 0
        for mod in mods:
            match = armour_expr.match(mod)
            if match:
                total += float(match.group(1))
        return armour * (120 + total) / (quality + 100 + total)

    @staticmethod
    def get_item_evasion(quality, modifiable, mods, evasion):
        if not modifiable or quality == 20:
            return evasion

        total = 0
        for mod in mods:
            match = evasion_expr.match(mod)
            if match:
                total += float(match.group(1))
        return evasion * (120 + total) / (quality + 100 + total)

    def get_item_class(self):
        global superior_expr
        base_line = superior_expr.sub('', self.base, 1)
        item_class = ItemClass(0)
        try:
            # this will fail for magic items with affixes since we dont strip those
            item_class = ItemClass[ItemCollection.base_type_to_id[base_line]]
        except KeyError:
            match = dir_expr.match(self.icon)
            # seems to be accurate for the remaining cases
            if match:
                item_dirs = re.split(r'[/\\]', match.group(1))[:-1]
                for item_dir in item_dirs:
                    class_id = dir_to_id.get(item_dir)
                    if class_id:
                        item_class = ItemClass[class_id]
                        break
            # not all flasks have a traditional link
            elif 'Flask' in base_line:
                item_class = ItemClass.Flask

        if not item_class:
            logger.warn('Failed determining item class. item: {}, base_line: {}, link {}'.format(self.name, base_line, self.icon))

        return item_class

    def get_item_base(self):
        if self.iclass:
            bases = ItemCollection.get_base_types_by_class(self.iclass)
            typeLine = self._item['typeLine']
            for base in bases:
                if re.search(r'\b{}\b'.format(base), typeLine):
                    return base
        return None

    def get_max_sockets(self):
        """ ignores item type, only considers ilvl """
        if self.ilvl >= 50:
            return 6
        if self.ilvl >= 35:
            return 5
        if self.ilvl >= 25:
            return 4
        if self.ilvl >= 2:
            return 3
        return 2

    def get_type_max_sockets(self):
        iclass = self.iclass
        # if self.name in ItemCollection.SIX_LINK_EXCEPTIONS:
        #     return 6
        if (ItemClass.OneHandWeapon | ItemClass.Shield) & iclass == iclass:
            return 3
        if (ItemClass.BodyArmour | ItemClass.TwoHandWeapon) & iclass == iclass:
            return 6
        if (ItemClass.Helmet | ItemClass.Boots | ItemClass.Gloves) & iclass == iclass:
            return 4
        # if iclass & (ItemClass.Ring | ItemClass.Amulet) != 0:
        if (ItemClass.Ring | ItemClass.Amulet) & iclass == iclass:
            return 1  # Unset Ring, and Black Maw Talisman
        return 0

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

class ItemRarity(IntEnum):
    Normal = ItemType.Normal
    Magic = ItemType.Magic
    Rare = ItemType.Rare
    Unique = ItemType.Unique
    Relic = ItemType.Relic

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