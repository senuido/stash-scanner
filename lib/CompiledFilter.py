from lib.ModFilter import ModFilterType
from lib.ModFilterGroup import get_mod_val
from lib.Utility import RE_COMPILED_TYPE
from lib.CurrencyManager import cm

_FILTER_PRIO = {
    'base': 1,
    'name': 1,
    'price_min': 1,
    'price_max': 1,
    'ilvl_min': 1,
    'ilvl_max': 1,
    'corrupted': 1,
    'modifiable': 1,
    'identified': 1,
    'crafted': 1,
    'enchanted': 1,
    # 'type': 1,
    'rarity': 1,
    'sockets_min': 1,
    'sockets_max': 1,
    'stacksize_min': 1,
    'stacksize_max': 1,
    'modcount_min': 1,
    'modcount_max': 1,
    'buyout': 1,

    'links_min': 1,
    'links_max': 1,

    'level_min': 2,
    'level_max': 2,
    'exp': 2,
    'quality_min': 2,
    'quality_max': 2,

    'aps_min': 2,
    'aps_max': 2,
    'crit_min': 2,
    'crit_max': 2,
    'block_min': 2,
    'block_max': 2,
    'pdps_min': 3,
    'edps_min': 3,
    'dps_min': 3,
    'pdps_max': 3,
    'edps_max': 3,
    'dps_max': 3,

    'es_min': 3,
    'armour_min': 3,
    'evasion_min': 3,
    'es_max': 3,
    'armour_max': 3,
    'evasion_max': 3,

    'iclass': 3,

    'fgs': 5
}


class CompiledFilter:
    # __slots__ = _FILTER_PRIO.keys() | {'fltr', 'comp', 'enabled', 'crit_ordered'}
    __slots__ = ('rarity', 'armour_max', 'crafted', 'sockets_min', 'pdps_min', 'buyout', 'links_max', 'corrupted', 'block_min', 'stacksize_min', 'quality_max', 'crit_min', 'ilvl_min', 'es_max', 'base', 'aps_min', 'ilvl_max', 'crit_ordered', 'links_min', 'modifiable', 'armour_min', 'level_max', 'price_min', 'aps_max', 'modcount_min', 'edps_max', 'iclass', 'evasion_max', 'stacksize_max', 'enabled', 'identified', 'fltr', 'crit_max', 'sockets_max', 'quality_min', 'modcount_max', 'block_max', 'level_min', 'es_min', 'price_max', 'comp', 'dps_max', 'dps_min', 'enchanted', 'exp', 'pdps_max', 'name', 'fgs', 'evasion_min', 'edps_min')

    def __init__(self, fltr, comp):
        self.fltr = fltr
        self.comp = comp
        self.enabled = fltr.enabled
        self.crit_ordered = sorted(comp.keys(), key=lambda k: _FILTER_PRIO[k])

    def __str__(self):
        return self.getDisplayTitle()

    def finalize(self):
        for att in _FILTER_PRIO:
            setattr(self, att, self.comp.get(att, None))

    def getDisplayPrice(self):
        if 'price_max' not in self.comp:  # or self.comp['price'] <= 0:
            return ''

        return cm.toDisplayPrice(self.comp['price_max'])

    def getDisplayTitle(self, inc_price=False):
        title = self.fltr.title

        if inc_price:
            price = self.getDisplayPrice()

            if price:
                title = "{} ({})".format(self.fltr.title, price)

        return title


    def _checkNames(self, c_name, names):
        for name in names:
            if name:
                if name[0] == name[-1] == '"':
                # if name.startswith('"') and name.endswith('"'):
                    if name[1:-1] == c_name:
                        return True
                elif name in c_name:
                    return True

        return False

    def checkItem(self, item):
        if self.rarity is not None and item.rarity not in self.rarity:
            return False
        if self.price_min is not None and item.c_price is not None and item.c_price < self.price_min:
            return False
        if self.price_max is not None and item.c_price is not None and item.c_price > self.price_max:
            return False
        if self.buyout is not None and self.buyout != item.buyout:
            return False

        if self.name is not None and not self._checkNames(item.c_name, self.name):
            return False
        if self.links_min is not None and self.links_min > item.links_count:
            return False
        if self.links_max is not None and self.links_max < item.links_count:
            return False

        if self.base is not None and self.base not in item.c_base:
            return False
        if self.ilvl_min is not None and self.ilvl_min > item.ilvl:
            return False
        if self.ilvl_max is not None and self.ilvl_max < item.ilvl:
            return False
        if self.corrupted is not None and self.corrupted != item.corrupted:
            return False
        if self.modifiable is not None and self.modifiable != item.modifiable:
            return False
        if self.identified is not None and self.identified != item.identified:
            return False
        if self.crafted is not None and self.crafted != item.crafted:
            return False
        if self.enchanted is not None and self.enchanted != item.enchanted:
            return False
        if self.sockets_min is not None and self.sockets_min > item.sockets_count:
            return False
        if self.sockets_max is not None and self.sockets_max < item.sockets_count:
            return False
        if self.stacksize_min is not None and self.stacksize_min > item.stacksize:
            return False
        if self.stacksize_max is not None and self.stacksize_max < item.stacksize:
            return False

        if self.modcount_min is not None and self.modcount_min > item.modcount:
            return False
        if self.modcount_max is not None and self.modcount_max < item.modcount:
            return False

        if self.iclass is not None and self.iclass & item.iclass != item.iclass:
            return False

        if self.level_min is not None and self.level_min > max(item.level, item.tier):
            return False
        if self.level_max is not None and self.level_max < max(item.level, item.tier):
            return False

        if self.exp is not None and self.exp > item.exp:
            return False
        if self.quality_min is not None and self.quality_min > item.quality:
            return False
        if self.quality_max is not None and self.quality_max < item.quality:
            return False

        if self.es_min is not None and self.es_min > item.es:
            return False
        if self.es_max is not None and self.es_max < item.es:
            return False
        if self.armour_min is not None and self.armour_min > item.armour:
            return False
        if self.armour_max is not None and self.armour_max < item.armour:
            return False
        if self.evasion_min is not None and self.evasion_min > item.evasion:
            return False
        if self.evasion_max is not None and self.evasion_max < item.evasion:
            return False

        if self.dps_min is not None and self.dps_min > item.dps:
            return False
        if self.dps_max is not None and self.dps_max < item.dps:
            return False
        if self.edps_min is not None and self.edps_min > item.edps:
            return False
        if self.edps_max is not None and self.edps_max < item.edps:
            return False
        if self.pdps_min is not None and self.pdps_min > item.pdps:
            return False
        if self.pdps_max is not None and self.pdps_max < item.pdps:
            return False

        if self.aps_min is not None and self.aps_min > item.aps:
            return False
        if self.aps_max is not None and self.aps_max < item.aps:
            return False
        if self.crit_min is not None and self.crit_min > item.crit:
            return False
        if self.crit_max is not None and self.crit_max < item.crit:
            return False
        if self.block_min is not None and self.block_min > item.block:
            return False
        if self.block_max is not None and self.block_max < item.block:
            return False

        if self.fgs is not None:
            for fg in self.fgs:
                if not fg.checkMods(item):
                    return False

        return True

    # def checkItem_old(self, item):
    #     for key in self.crit_ordered:
    #         # if key == "type":
    #         #     if item.type not in self.comp[key]:
    #         #         return False
    #         if key == "rarity":
    #             if item.rarity not in self.comp[key]:
    #                 return False
    #         elif key == "price_min":
    #             if item.c_price is not None and item.c_price < self.comp[key]:
    #                     return False
    #         elif key == "price_max":
    #             if item.c_price is not None and item.c_price > self.comp[key]:
    #                     return False
    #         elif key == "name":
    #             # if not any(name in item.c_name for name in self.comp[key]):
    #             #     return False
    #             if not self._checkNames(item.c_name, self.comp[key]):
    #                 return False
    #         elif key == "iclass":
    #             if self.comp[key] & item.iclass != item.iclass:
    #                 return False
    #         elif key == "base":
    #             if self.comp[key] not in item.c_base:
    #                 return False
    #         elif key == "ilvl_min":
    #             if self.comp[key] > item.ilvl:
    #                 return False
    #         elif key == "ilvl_max":
    #             if self.comp[key] < item.ilvl:
    #                 return False
    #         elif key == "corrupted":
    #             if self.comp[key] != item.corrupted:
    #                 return False
    #         elif key == "modifiable":
    #             if self.comp[key] != item.modifiable:
    #                 return False
    #         elif key == "identified":
    #             if self.comp[key] != item.identified:
    #                 return False
    #         elif key == "crafted":
    #             if self.comp[key] != item.crafted:
    #                 return False
    #         elif key == "enchanted":
    #             if self.comp[key] != item.enchanted:
    #                 return False
    #         elif key == "sockets_min":
    #             if self.comp[key] > item.sockets_count:
    #                 return False
    #         elif key == "sockets_max":
    #             if self.comp[key] < item.sockets_count:
    #                 return False
    #         elif key == "links_min":
    #             if self.comp[key] > item.links_count:
    #                 return False
    #         elif key == "links_max":
    #             if self.comp[key] < item.links_count:
    #                 return False
    #         elif key == "stacksize_min":
    #             if self.comp[key] > item.stacksize:
    #                 return False
    #         elif key == "stacksize_max":
    #             if self.comp[key] < item.stacksize:
    #                 return False
    #         elif key == "modcount_min":
    #             if self.comp[key] > item.modcount:
    #                 return False
    #         elif key == "modcount_max":
    #             if self.comp[key] < item.modcount:
    #                 return False
    #         elif key == "buyout":
    #             if self.comp[key] != item.buyout:
    #                 return False
    #         elif key == "fgs":
    #             for fg in self.comp[key]:
    #                 if not fg.checkMods(item):
    #                     return False
    #         elif key == "level_min":
    #             if self.comp[key] > item.level:
    #                 return False
    #         elif key == "level_max":
    #             if self.comp[key] < item.level:
    #                 return False
    #         elif key == "exp":
    #             if self.comp[key] > item.exp:
    #                 return False
    #         elif key == "quality_min":
    #             if self.comp[key] > item.quality:
    #                 return False
    #         elif key == "quality_max":
    #             if self.comp[key] < item.quality:
    #                 return False
    #
    #         elif key == "es_min":
    #             if self.comp[key] > item.es:
    #                 return False
    #         elif key == "es_max":
    #             if self.comp[key] < item.es:
    #                 return False
    #         elif key == "armour_min":
    #             if self.comp[key] > item.armour:
    #                 return False
    #         elif key == "armour_max":
    #             if self.comp[key] < item.armour:
    #                 return False
    #         elif key == "evasion_min":
    #             if self.comp[key] > item.evasion:
    #                 return False
    #         elif key == "evasion_max":
    #             if self.comp[key] < item.evasion:
    #                 return False
    #
    #         elif key == "edps_min":
    #             if self.comp[key] > item.edps:
    #                 return False
    #         elif key == "edps_max":
    #             if self.comp[key] < item.edps:
    #                 return False
    #         elif key == "pdps_min":
    #             if self.comp[key] > item.pdps:
    #                 return False
    #         elif key == "pdps_max":
    #             if self.comp[key] < item.pdps:
    #                 return False
    #         elif key == "dps_min":
    #             if self.comp[key] > item.dps:
    #                 return False
    #         elif key == "dps_max":
    #             if self.comp[key] < item.dps:
    #                 return False
    #
    #         elif key == 'aps_min':
    #             if self.comp[key] > item.aps:
    #                 return False
    #         elif key == 'aps_max':
    #             if self.comp[key] < item.aps:
    #                 return False
    #         elif key == 'crit_min':
    #             if self.comp[key] > item.crit:
    #                 return False
    #         elif key == 'crit_max':
    #             if self.comp[key] < item.crit:
    #                 return False
    #         elif key == 'block_min':
    #             if self.comp[key] > item.block:
    #                 return False
    #         elif key == 'block_max':
    #             if self.comp[key] < item.block:
    #                 return False
    #
    #     return True

    def getDisplayTotals(self, item):
        totals = []

        for fg in self.comp.get('fgs', []):
            for mf in fg.mfs:
                if mf.type in (ModFilterType.Pseudo, ModFilterType.Total):
                    val = get_mod_val(item, mf)
                    if val:
                        if isinstance(mf.expr, RE_COMPILED_TYPE):
                            expr = mf.expr.pattern
                        else:
                            expr = mf.expr
                        totals.append((mf.type, expr, val))
        return set(totals)