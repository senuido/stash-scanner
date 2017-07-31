import re
from abc import ABCMeta, abstractmethod
from enum import Enum

from lib.ItemHelper import Item
from lib.ModFilter import ModFilter, ModFilterType


class ModFilterGroup(metaclass=ABCMeta):
    __slots__ = ('mfs')

    def __init__(self, mod_filters=None):
        self.mfs = [] if mod_filters is None else mod_filters

    def toDict(self):
        return {
            'type': self.getType().value,
            'mfs': [mf.toDict() for mf in self.mfs]}

    def fromDict(self, data):
        self.mfs = [ModFilter.fromData(mf) for mf in data.get('mfs', [])]

    def addModFilter(self, mf):
        self.mfs.append(mf)

    def removeModFilter(self, index):
        del self.mfs[index]

    @abstractmethod
    def getType(self):
        pass

    @abstractmethod
    def checkMods(self, item):
        pass


class CountFilterGroup(ModFilterGroup):
    __slots__ = ('match_min', 'match_max')
    def __init__(self, mod_filters=None, match_min=None, match_max=None):
        super().__init__(mod_filters)
        self.match_min = match_min
        self.match_max = match_max

    def fromDict(self, data):
        super().fromDict(data)
        self.match_min = data.get('match_min', None)
        self.match_max = data.get('match_max', None)

    def toDict(self):
        data = super().toDict()
        data['match_min'] = self.match_min
        data['match_max'] = self.match_max
        return data

    def checkMods(self, item):
        match_min = len(self.mfs) if self.match_min is None else self.match_min
        match_max = len(self.mfs) if self.match_max is None else self.match_max
        return checkmods_count(item, self.mfs, match_min, match_max)

    def getType(self):
        return FilterGroupType.Count


class AllFilterGroup(ModFilterGroup):
    __slots__ = ()

    def __init__(self, mod_filters=None):
        super().__init__(mod_filters)

    def checkMods(self, item):
        return checkmods_count(item, self.mfs, len(self.mfs), len(self.mfs))

    def getType(self):
        return FilterGroupType.All


class NoneFilterGroup(ModFilterGroup):
    __slots__ = ()

    def __init__(self, mod_filters=None):
        super().__init__(mod_filters)

    def checkMods(self, item):
        return checkmods_count(item, self.mfs, 0, 0)

    def getType(self):
        return FilterGroupType.Nothing


class FilterGroupType(Enum):
    All = "all"
    Count = "count"
    Nothing = "none"


class FilterGroupFactory:
    @staticmethod
    def create(fg_type, data):
        if fg_type == FilterGroupType.All:
            fg = AllFilterGroup()
        elif fg_type == FilterGroupType.Count:
            fg = CountFilterGroup()
        elif fg_type == FilterGroupType.Nothing:
            fg = NoneFilterGroup()
        else:
            raise ValueError('Invalid filter group type: {}'.format(fg_type))

        fg.fromDict(data)
        return fg


def checkmods_count(item, mfs, match_min, match_max):
    if match_max < match_min:
        return False

    matched = 0
    for mf in mfs:
        mf_matched = False
        skip_vals = mf.min is None and mf.max is None
        mod_val = get_mod_val(item, mf, skip_vals)

        if mod_val:  # if the total is 0, we treat it as non-match
            if skip_vals:
                mf_matched = True
            else:
                min_val = mod_val if mf.min is None else mf.min
                max_val = mod_val if mf.max is None else mf.max
                mf_matched = min_val <= mod_val <= max_val

        if mf_matched:
            matched += 1

            if matched > match_max:
                return False
            if matched >= match_min:
                return True

    return match_min <= matched <= match_max

def get_mod_val(item, mf, skip_vals=False):
    expr = mf.expr
    mod_val = 0

    if mf.type == ModFilterType.Pseudo:
        if expr not in PSEUDO_MODS:
            return 0

        mod_exprs = COMPILED_PSEUDO_MODS[expr]
        if mod_exprs:
            for mod_expr in mod_exprs:
                mod_val += Item.get_mod_total(mod_expr, item.mods, skip_vals)

                if mod_val and skip_vals:
                    break
        elif expr == '# Elemental Resistances':
            if item.ele_res:
                mod_val = 3
            else:
                mod_val += 1 if item.cres else 0
                mod_val += 1 if item.fres else 0
                mod_val += 1 if item.lres else 0
        elif expr == '# Resistances':
            if item.ele_res:
                mod_val = 3
            else:
                mod_val += 1 if item.cres else 0
                mod_val += 1 if item.fres else 0
                mod_val += 1 if item.lres else 0
            mod_val += 1 if item.chres else 0
        elif expr == '+#% total Elemental Resistance':
            mod_val = item.ele_res * 3 + item.cres + item.fres + item.lres
        elif expr == '+#% total Resistance':
            mod_val = item.ele_res * 3 + item.cres + item.fres + item.lres + item.chres
        elif expr == '(total) +#% to all Elemental Resistances':
            mod_val = item.ele_res + min(item.cres, item.fres, item.lres)
        elif expr == '(total) +#% to Cold Resistance':
            mod_val = item.cres
        elif expr == '(total) +#% to Fire Resistance':
            mod_val = item.fres
        elif expr == '(total) +#% to Lightning Resistance':
            mod_val = item.lres
        elif expr == '(total) +# to all Attributes':
            mod_val = item.attributes_bonus + min(item.strength_bonus, item.dex_bonus, item.int_bonus)
        elif expr == '(total) +# to Strength':
            mod_val = item.attributes_bonus + item.strength_bonus
        elif expr == '(total) +# to Dexterity':
            mod_val = item.attributes_bonus + item.dex_bonus
        elif expr == '(total) +# to Intelligence':
            mod_val = item.attributes_bonus + item.int_bonus
        elif expr == '(total) +# to maximum Life':
            mod_val = item.life + (item.strength_bonus + item.attributes_bonus) / 2

    else:
        mods_list = get_mods_by_type(item, mf.type)
        mod_val = Item.get_mod_total(expr, mods_list, skip_vals)

    return mod_val

def get_mods_by_type(item, mf_type):
    if mf_type == ModFilterType.Total:
        return item.mods
    elif mf_type == ModFilterType.Explicit:
        return item.explicit
    elif mf_type == ModFilterType.Implicit:
        return item.implicit
    elif mf_type == ModFilterType.Enchant:
        return item.enchant
    elif mf_type == ModFilterType.Crafted:
        return item.craft
    elif mf_type == ModFilterType.Leaguestone:
        # # convert to format string as appears in item
        # pat = expr.pattern
        # for i in range(expr.groups)
        #     pat = pat.replace('([0-9]+)', '%' + str(i), 1)
        #
        # item.get_property_value()
        return item.formatted_properties
    elif mf_type == ModFilterType.Prophecy:
        return (item.prophecy, )

    raise ValueError('Unrecognized mod filter type: {}'.format(mf_type))

PSEUDO_MODS = {
    '# Elemental Resistances': None,
    '# Resistances': None,
    '+#% total Elemental Resistance': None,
    '+#% total Resistance': None,

    '(total) +#% to all Elemental Resistances': None,
    '(total) +#% to Cold Resistance': None,
    '(total) +#% to Fire Resistance': None,
    '(total) +#% to Lightning Resistance': None,
    '(total) +# to all Attributes': None,
    '(total) +# to Dexterity': None,
    '(total) +# to Intelligence': None,
    '(total) +# to Strength': None,
    '(total) +# to maximum Life': None,

    '(total) #% increased Elemental Damage with Weapons': ('([0-9]+)% increased Elemental Damage(?: with Weapons)?$', ),
    '(total) #% increased Cold Damage with Weapons': ('([0-9]+)% increased (?:Elemental|Cold) Damage(?: with Weapons)?$', ),
    '(total) #% increased Fire Damage with Weapons': ('([0-9]+)% increased (?:Elemental|Fire) Damage(?: with Weapons)?$', ),
    '(total) #% increased Lightning Damage with Weapons': ('([0-9]+)% increased (?:Elemental|Lightning) Damage(?: with Weapons)?$', ),
    '(total) #% increased Cold Spell Damage': ('([0-9]+)% increased (?:Elemental|Spell|Cold) Damage$', ),
    '(total) #% increased Fire Spell Damage': ('([0-9]+)% increased (?:Elemental|Spell|Fire) Damage$', ),
    '(total) #% increased Lightning Spell Damage': ('([0-9]+)% increased (?:Elemental|Spell|Lightning) Damage$', ),
    '(total) #% increased Burning Damage': ('([0-9]+)% increased (?:Elemental|Fire|Burning) Damage$', ),
    '(total) #% increased Critical Strike Chance for Spells': ('([0-9]+)% increased Global Critical Strike Chance$', '([0-9]+)% increased Critical Strike Chance for Spells$'),
    '(total) #% increased Fire Area Damage': ('([0-9]+)% increased (?:Elemental|Fire|Area) Damage$', ),

    '(total) +# to Level of Socketed Aura Gems': ('([\-+][0-9]+) to Level of Socketed(?: Aura)? Gems$', ),
    '(total) +# to Level of Socketed Bow Gems': ('([\-+][0-9]+) to Level of Socketed(?: Bow)? Gems$', ),
    '(total) +# to Level of Socketed Chaos Gems': ('([\-+][0-9]+) to Level of Socketed(?: Chaos)? Gems$', ),
    '(total) +# to Level of Socketed Elemental Gems': ('([\-+][0-9]+) to Level of Socketed(?: Elemental)? Gems$', ),
    '(total) +# to Level of Socketed Cold Gems': ('([\-+][0-9]+) to Level of Socketed(?: Cold)? Gems$', ),
    '(total) +# to Level of Socketed Fire Gems': ('([\-+][0-9]+) to Level of Socketed(?: Fire)? Gems$', ),
    '(total) +# to Level of Socketed Lightning Gems': ('([\-+][0-9]+) to Level of Socketed(?: Lightning)? Gems$', ),
    '(total) +# to Level of Socketed Melee Gems': ('([\-+][0-9]+) to Level of Socketed(?: Melee)? Gems$', ),
    '(total) +# to Level of Socketed Minion Gems': ('([\-+][0-9]+) to Level of Socketed(?: Minion)? Gems$', ),
    '(total) +# to Level of Socketed Movement Gems': ('([\-+][0-9]+) to Level of Socketed(?: Movement)? Gems$', ),
    '(total) +# to Level of Socketed Spell Gems': ('([\-+][0-9]+) to Level of Socketed(?: Spell)? Gems$', ),
    '(total) +# to Level of Socketed Support Gems': ('([\-+][0-9]+) to Level of Socketed(?: Support)? Gems$', ),
    '(total) +# to Level of Socketed Strength Gems': ('([\-+][0-9]+) to Level of Socketed(?: Strength)? Gems$', ),
    '(total) +# to Level of Socketed Vaal Gems': ('([\-+][0-9]+) to Level of Socketed(?: Vaal)? Gems$', ),

    '(total) Adds # Damage to Attacks': ('Adds ([0-9]+) to ([0-9]+) (?:Physical|Chaos|Cold|Fire|Lightning) Damage(?: to Attacks)?$', ),
    '(total) Adds # Elemental Damage to Attacks': ('Adds ([0-9]+) to ([0-9]+) (?:Cold|Fire|Lightning) Damage(?: to Attacks)?$', ),
    '(total) Adds # Damage to Spells': ('Adds ([0-9]+) to ([0-9]+) (?:Chaos|Cold|Fire|Lightning) Damage to Spells$', ),
    '(total) Adds # Elemental Damage to Spells': ('Adds ([0-9]+) to ([0-9]+) (?:Cold|Fire|Lightning) Damage to Spells$', ),
    '(total) Adds # Fire Damage to Attacks': ('Adds ([0-9]+) to ([0-9]+) Fire Damage(?: to Attacks)?$', ),
    '(total) Adds # Physical Damage to Attacks': ('Adds ([0-9]+) to ([0-9]+) Physical Damage(?: to Attacks)?$', ),
}

COMPILED_PSEUDO_MODS = {k: [re.compile(mod) for mod in PSEUDO_MODS[k]] if PSEUDO_MODS[k] else None for k in PSEUDO_MODS}
