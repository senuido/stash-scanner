from lib.ModFilter import ModFilterType
from lib.ModFilterGroup import get_mod_val
from lib.Utility import RE_COMPILED_TYPE

_FILTER_PRIO = {
    'base': 1,
    'price_min': 1,
    'price_max': 1,
    'ilvl_min': 1,
    'ilvl_max': 1,
    'corrupted': 1,
    'modifiable': 1,
    'identified': 1,
    'crafted': 1,
    'enchanted': 1,
    'type': 1,
    'sockets_min': 1,
    'sockets_max': 1,
    'stacksize_min': 1,
    'stacksize_max': 1,
    'modcount_min': 1,
    'modcount_max': 1,
    'buyout': 1,

    'level_min': 1,
    'level_max': 1,
    'exp': 1,
    'quality_min': 1,
    'quality_max': 1,

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

    'links_min': 2,
    'links_max': 2,
    'name': 2,

    'fgs': 5
}
from lib.CurrencyManager import cm



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
        if 'price_max' not in self.comp:  # or self.comp['price'] <= 0:
            return ''

        return cm.toDisplayPrice(self.comp['price_max'])

    def getDisplayTitle(self):
        title = self.fltr.title

        # price = self.getDisplayPrice()
        #
        # if price:
        #     title = "{} ({})".format(self.fltr.title, price)

        return title

    def checkItem(self, item):
        for key in self.crit_ordered:
            if key == "type":
                if item.type not in self.comp[key]:
                    return False
            elif key == "price_min":
                if item.c_price is not None and item.c_price < self.comp[key]:
                        return False
            elif key == "price_max":
                if item.c_price is not None and item.c_price > self.comp[key]:
                        return False
            elif key == "name":
                if not any(name in item.c_name for name in self.comp[key]):
                    return False
            elif key == "base":
                if self.comp[key] not in item.base:
                    return False
            elif key == "ilvl_min":
                if self.comp[key] > item.ilvl:
                    return False
            elif key == "ilvl_max":
                if self.comp[key] < item.ilvl:
                    return False
            elif key == "corrupted":
                if self.comp[key] != item.corrupted:
                    return False
            elif key == "modifiable":
                if not self.comp[key] != (item.mirrored or item.corrupted):
                    return False
            elif key == "identified":
                if self.comp[key] != item.identified:
                    return False
            elif key == "crafted":
                if self.comp[key] != item.crafted:
                    return False
            elif key == "enchanted":
                if self.comp[key] != item.enchanted:
                    return False
            elif key == "sockets_min":
                if self.comp[key] > item.sockets_count:
                    return False
            elif key == "sockets_max":
                if self.comp[key] < item.sockets_count:
                    return False
            elif key == "links_min":
                if self.comp[key] > item.links_count:
                    return False
            elif key == "links_max":
                if self.comp[key] < item.links_count:
                    return False
            elif key == "stacksize_min":
                if self.comp[key] > item.stacksize:
                    return False
            elif key == "stacksize_max":
                if self.comp[key] < item.stacksize:
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
            elif key == "fgs":
                for fg in self.comp[key]:
                    if not fg.checkMods(item):
                        return False
            elif key == "level_min":
                if self.comp[key] > item.level:
                    return False
            elif key == "level_max":
                if self.comp[key] < item.level:
                    return False
            elif key == "exp":
                if self.comp[key] > item.exp:
                    return False
            elif key == "quality_min":
                if self.comp[key] > item.quality:
                    return False
            elif key == "quality_max":
                if self.comp[key] < item.quality:
                    return False

            elif key == "es_min":
                if self.comp[key] > item.es:
                    return False
            elif key == "es_max":
                if self.comp[key] < item.es:
                    return False
            elif key == "armour_min":
                if self.comp[key] > item.armour:
                    return False
            elif key == "armour_max":
                if self.comp[key] < item.armour:
                    return False
            elif key == "evasion_min":
                if self.comp[key] > item.evasion:
                    return False
            elif key == "evasion_max":
                if self.comp[key] < item.evasion:
                    return False

            elif key == "edps_min":
                if self.comp[key] > item.edps:
                    return False
            elif key == "edps_max":
                if self.comp[key] < item.edps:
                    return False
            elif key == "pdps_min":
                if self.comp[key] > item.pdps:
                    return False
            elif key == "pdps_max":
                if self.comp[key] < item.pdps:
                    return False
            elif key == "dps_min":
                if self.comp[key] > item.dps:
                    return False
            elif key == "dps_max":
                if self.comp[key] < item.dps:
                    return False

        return True

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