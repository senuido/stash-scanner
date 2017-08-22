from itertools import chain

from lib.CompiledFilter import CompiledFilter
from lib.ItemClass import ItemClass
from lib.ItemHelper import ItemType, Item, ItemRarity
from lib.ModFilterGroup import FilterGroupType
from lib.ModsHelper import mod_helper
from lib.Utility import RE_COMPILED_TYPE, config, namify


class SearchParams:
    _atts = ['league','type','base','name','dmg_min','dmg_max','aps_min','aps_max','crit_min','crit_max','dps_min','dps_max','edps_min','edps_max','pdps_min','pdps_max','armour_min','armour_max','evasion_min','evasion_max','shield_min','shield_max','block_min','block_max','sockets_min','sockets_max','link_min','link_max','sockets_r','sockets_g','sockets_b','sockets_w','linked_r','linked_g','linked_b','linked_w','rlevel_min','rlevel_max','rstr_min','rstr_max','rdex_min','rdex_max','rint_min','rint_max','q_min','q_max','level_min','level_max','ilvl_min','ilvl_max','rarity','seller','thread','identified','corrupted','online','has_buyout','altart','capquality','buyout_min','buyout_max','buyout_currency','crafted','enchanted']
    # _defaults = {'online': 'x', 'capquality': 'x'}
    _cb_atts = ['altart', 'online', 'capquality']
    _bool_atts = ['has_buyout', 'identified', 'corrupted', 'crafted', 'enchanted']
    _fixed_types = {ItemClass.OneHandWeapon: '1h', ItemClass.TwoHandWeapon: '2h', ItemClass.MapFragment: 'Vaal Fragments', ItemClass.FishingRod: 'Fishing Rods'}
    _valid_types = {'Staff', 'Leaguestone', 'Body Armour', 'Dagger', 'Prophecy', '2h', 'Belt', 'Ring', 'Two Hand Axe', 'Gem', 'One Hand Sword', 'Currency', 'Claw', 'Boots', 'One Hand Axe', 'Divination Card', 'Quiver', '1h', 'Vaal Fragments', 'Two Hand Sword', 'Map', 'Shield', 'Two Hand Mace', 'Fishing Rods', 'One Hand Mace', 'Gloves', 'Breach', 'Helmet', 'Amulet', 'Sceptre', 'Essence', 'Jewel', 'Wand', 'Bow', 'Flask'}
    __slots__ = tuple(_atts + ['fgs'])

    def __init__(self):
        for att in self.__slots__:
            setattr(self, att, None)

    @classmethod
    def genFilterSearch(cls, item, cf):
        if not isinstance(item, Item):
            raise TypeError('item is expected to be of type Item')
        if not isinstance(cf, CompiledFilter):
            raise TypeError('cf is expected to be of type CompiledFilter')

        sp = cls()
        sp.league = config.league
        # sp.dmg_min = cf.dmg_min
        # sp.dmg_max = cf.dmg_max
        sp.aps_min = cf.aps_min
        sp.aps_max = cf.aps_max
        sp.crit_min = cf.crit_min
        sp.crit_max = cf.crit_max
        sp.dps_min = cf.dps_min
        sp.dps_max = cf.dps_max
        sp.edps_min = cf.edps_min
        sp.edps_max = cf.edps_max
        sp.pdps_min = cf.pdps_min
        sp.pdps_max = cf.pdps_max
        sp.armour_min = cf.armour_min
        sp.armour_max = cf.armour_max
        sp.evasion_min = cf.evasion_min
        sp.evasion_max = cf.evasion_max
        sp.shield_min = cf.es_min
        sp.shield_max = cf.es_max
        sp.block_min = cf.block_min
        sp.block_max = cf.block_max
        sp.sockets_min = cf.sockets_min
        sp.sockets_max = cf.sockets_max
        sp.link_min = cf.links_min
        sp.link_max = cf.links_max

        sp.q_min = cf.quality_min
        sp.q_max = cf.quality_max
        sp.level_min = cf.level_min
        sp.level_max = cf.level_max
        sp.ilvl_min = cf.ilvl_min
        sp.ilvl_max = cf.ilvl_max

        # sp.sockets_r = cf.sockets_r
        # sp.sockets_g = cf.sockets_g
        # sp.sockets_b = cf.sockets_b
        # sp.sockets_w = cf.sockets_w
        # sp.linked_r = cf.linked_r
        # sp.linked_g = cf.linked_g
        # sp.linked_b = cf.linked_b
        # sp.linked_w = cf.linked_w
        # sp.rlevel_min = cf.rlevel_min
        # sp.rlevel_max = cf.rlevel_max
        # sp.rstr_min = cf.rstr_min
        # sp.rstr_max = cf.rstr_max
        # sp.rdex_min = cf.rdex_min
        # sp.rdex_max = cf.rdex_max
        # sp.rint_min = cf.rint_min
        # sp.rint_max = cf.rint_max

        # sp.seller = None
        # sp.thread = None
        # sp.altart = None

        sp.identified = cf.identified
        sp.corrupted = cf.corrupted if cf.corrupted is not None else cf.modifiable
        sp.crafted = cf.crafted
        sp.enchanted = cf.enchanted

        sp.online = True
        sp.capquality = True

        sp.has_buyout = cf.buyout

        # # TODO: limit prices?
        # sp.buyout_min = cf.price_min
        # sp.buyout_max = cf.price_max
        # sp.buyout_currency = 'chaos'

        sp.base = item.get_item_base() if cf.base else None
        sp.type = cf.iclass

        if cf.rarity:
            if len(cf.rarity) == 1:
                rarity = cf.rarity[0]
            else:  # show all rarities instead of choosing first one or item's rarity
                rarity = None
            sp.rarity = rarity

        # the search engine only accepts full words in name field, according to the tutorial
        # any partial names from filters which arent considered words won't work properly
        sp.name = cls._find_matched_name(item, cf)
        sp.fgs = cf.fgs

        return sp

    @classmethod
    def genItemSearch(cls, item, cf):
        if not isinstance(item, Item):
            raise TypeError('item is expected to be of type Item')
        if not isinstance(cf, CompiledFilter):
            raise TypeError('cf is expected to be of type CompiledFilter')

        sp = cls()
        sp.league = config.league

        sp.identified = cf.identified
        sp.rarity = item.rarity

        sp.online = True
        sp.capquality = True
        sp.has_buyout = True

        if item.links_count == 6:
            sp.link_min = item.links_count

        # if not item.modifiable:
        #     sp.corrupted = True
        sp.corrupted = not item.modifiable

        if item.rarity in (ItemRarity.Unique, ItemRarity.Relic):
            sp.name = item.name
            if item.links_count >= 5:
                sp.link_min = item.links_count
        else:
            sp.name = item.get_item_base()

        if item.iclass:
            if ItemClass.Gem & item.iclass == item.iclass:
                if item.level < 18:
                    sp.level_min = item.level - 2
                else:
                    sp.level_min = item.level

                if item.quality > 20:
                    sp.q_min = item.quality
                else:
                    sp.q_min = max(item.quality - 3, 0)



        # # TODO: limit prices?
        # sp.buyout_min = cf.price_min
        # sp.buyout_max = cf.price_max
        # sp.buyout_currency = 'chaos'

        sp.fgs = cf.fgs

        return sp

    def convert(self):
        base_params = {}
        for att in self._atts:
            val = getattr(self, att, None)
            if att == 'type':
                itype = self._convert_type(val)
                val = itype if itype in self._valid_types else ''
            elif att == 'rarity':
                try:
                    val = ItemRarity(val).name.lower()
                except ValueError:
                    val = ''
            elif val is not None:
                if att in self._bool_atts:
                    val = '1' if val else '0'
                elif att in self._cb_atts:
                    val = 'x' if val else ''

            base_params[att] = val or ''

        fgs = self.fgs or []
        fgs_params = list(chain.from_iterable((self._fgToParam(fg) for fg in fgs)))

        return list(base_params.items()) + fgs_params

    @staticmethod
    def _find_matched_name(item, cf):
        if cf.name:
            for name in cf.name:  # cf names are lower case, so is item.c_name
                if name and name[0] == name[-1] == '"':
                    if name[1:-1] == item.c_name:
                        return item.name
                elif name in item.c_name:
                    return name
        return None

    @staticmethod
    def _convert_type(iclass):
        if not iclass:
            return None

        if ItemClass.OneHandSword & iclass == iclass:
            iclass = ItemClass.OneHandSword
        elif iclass == ItemClass.MiscOneHandMace:
            iclass = ItemClass.OneHandMace
        # elif iclass == ItemClass.MiscMapItem:
        #     iclass = ItemClass.MapFragment  # not perfect

        if iclass in SearchParams._fixed_types:
            return SearchParams._fixed_types[iclass]

        return namify(iclass.name)

    # TODO: MOVE TO CLASSES?
    @staticmethod
    def _mfToParam(mf):
        # if compiled:
        # pseudo = text
        # others = re.compiled
        if isinstance(mf.expr, RE_COMPILED_TYPE):
            expr = mf.expr.pattern
        else:
            expr = mf.expr

        return [
            ('mod_name', mod_helper.modToParam(mf.type, expr)),
            ('mod_min', '' if mf.min is None else mf.min),
            ('mod_max', '' if mf.max is None else mf.max),
        ]

    @staticmethod
    def _fgToParam(fg):
        searchable_mfs = []
        for mf in fg.mfs:
            try:
                searchable_mfs.append(SearchParams._mfToParam(mf))
            except ValueError:
                pass

        g_min = ''
        g_max = ''

        if fg.getType() == FilterGroupType.Count:
            g_type = 'Count'
        elif fg.getType() == FilterGroupType.Nothing:
            g_type = 'None'
        else:
            g_type = 'And'

        if fg.getType() == FilterGroupType.Count:
            if fg.match_min is not None:
                g_min = fg.match_min
            if fg.match_max is not None:
                g_max = fg.match_max

        if not searchable_mfs:
            return []

        l = list(chain.from_iterable(searchable_mfs))
        l.extend([
            ('group_type', g_type),
            ('group_min', g_min),
            ('group_max', g_max),
            ('group_count', len(searchable_mfs))
        ])

        return l