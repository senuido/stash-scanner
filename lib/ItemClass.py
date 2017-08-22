from aenum import IntFlag, auto


class ItemClass(IntFlag):
    Amulet = auto()
    Belt = auto()
    BodyArmour = auto()
    Boots = auto()
    Bow = auto()
    Breach = auto()
    Claw = auto()
    Currency = auto()
    Dagger = auto()
    DivinationCard = auto()
    Essence = auto()
    FishingRod = auto()
    Flask = auto()
    Gem = auto()
    Gloves = auto()
    Helmet = auto()
    Jewel = auto()
    Leaguestone = auto()
    Map = auto()
    MapFragment = auto()
    MiscMapItem = auto()
    MiscOneHandMace = auto()
    MiscOneHandSword = auto()
    OneHandAxe = auto()
    Prophecy = auto()
    Quiver = auto()
    Ring = auto()
    Sceptre = auto()
    Shield = auto()
    Staff = auto()
    ThrustingOneHandSword = auto()
    TwoHandAxe = auto()
    TwoHandMace = auto()
    TwoHandSword = auto()
    UniqueFragment = auto()
    Wand = auto()
    OneHandSword = ThrustingOneHandSword | MiscOneHandSword
    OneHandMace = Sceptre | MiscOneHandMace
    OneHandWeapon = Claw | Wand | MiscOneHandMace | OneHandAxe | Dagger | ThrustingOneHandSword | Sceptre | MiscOneHandSword
    TwoHandWeapon = Bow | FishingRod | Staff | TwoHandAxe | TwoHandMace | TwoHandSword
    OffHand = Quiver | Shield
    Accessories = Belt | Amulet | Ring
    Armour = Gloves | BodyArmour | Boots | Helmet
    Weapon = OneHandWeapon | TwoHandWeapon


dir_to_id = {'MiscMapItems': 'MiscMapItem', 'Amulets': 'Amulet', 'Staves': 'Staff', 'Classic': 'Leaguestone', 'Divination': 'DivinationCard', 'TwoHandMace': 'TwoHandMace', 'FishingRod': 'FishingRod', 'Dagger': 'Dagger', 'Essence': 'Essence', 'Shield': 'Shield', 'Sceptre': 'Sceptre', 'Rings': 'Ring', 'Helmet': 'Helmet', 'Ring': 'Ring', 'Wands': 'Wand', 'TwoHandSwords': 'TwoHandSword', 'Daggers': 'Dagger', 'Bow': 'Bow', 'Wand': 'Wand', 'Rapiers': 'ThrustingOneHandSword', 'Maps': 'Map', 'Gloves': 'Gloves', 'Staff': 'Staff', 'Bows': 'Bow', 'Claws': 'Claw', 'Map': 'Map', 'OneHandMace': 'MiscOneHandMace', 'Belts': 'Belt', 'TwoHandAxes': 'TwoHandAxe', 'Piece': 'UniqueFragment', 'Flask': 'Flask', 'Helmets': 'Helmet', 'TwoHandSword': 'TwoHandSword', 'Currency': 'Currency', 'Quiver': 'Quiver', 'Essences': 'Essence', 'OneHandSwords': 'MiscOneHandSword', 'Jewel': 'Jewel', 'BodyArmours': 'BodyArmour', 'Prophecy': 'Prophecy', 'OneHandAxe': 'OneHandAxe', 'TwoHandAxe': 'TwoHandAxe', 'Breach': 'Breach', 'Sceptres': 'Sceptre', 'TwoHandMaces': 'TwoHandMace', 'Scepters': 'Sceptre', 'Amulet': 'Amulet', 'Gem': 'Gem', 'UniqueFragment': 'UniqueFragment', 'FishingRods': 'FishingRod', 'ThrustingOneHandSwords': 'ThrustingOneHandSword', 'Shields': 'Shield', 'MapFragment': 'MapFragment', 'Leaguestones': 'Leaguestone', 'Belt': 'Belt', 'Claw': 'Claw', 'OneHandAxes': 'OneHandAxe', 'DivinationCard': 'DivinationCard', 'MiscMapItem': 'MiscMapItem', 'BodyArmour': 'BodyArmour', 'MapFragments': 'MapFragment', 'Jewels': 'Jewel', 'StackableCurrency': 'Currency', 'OneHandSword': 'MiscOneHandSword', 'ThrustingOneHandSword': 'ThrustingOneHandSword', 'Boots': 'Boots', 'Leaguestone': 'Leaguestone', 'Quivers': 'Quiver', 'OneHandMaces': 'MiscOneHandMace', 'Flasks': 'Flask', 'Prophecies': 'Prophecy', 'Gems': 'Gem'}
id_to_name = {'MiscOneHandMace': 'One Hand Maces', 'TwoHandMace': 'Two Hand Maces', 'Dagger': 'Daggers', 'Essence': 'Essences', 'Shield': 'Shields', 'Sceptre': 'Sceptres', 'Accessories': 'Accessories', 'FishingRod': 'Fishing Rods', 'TwoHandWeapon': 'Two Handed Weapon', 'Breach': 'Breach', 'Wand': 'Wands', 'Gloves': 'Gloves', 'Staff': 'Staves', 'OffHand': 'Off-hand', 'Map': 'Maps', 'OneHandWeapon': 'One Handed Weapon', 'OneHandMace': 'One Hand Maces', 'Gem': 'Gems', 'OneHandSword': 'One Hand Swords', 'Flask': 'Flasks', 'MiscOneHandSword': 'One Hand Swords', 'Currency': 'Currency', 'Quiver': 'Quivers', 'Jewel': 'Jewel', 'Prophecy': 'Prophecies', 'OneHandAxe': 'One Hand Axes', 'TwoHandAxe': 'Two Hand Axes', 'Bow': 'Bows', 'MapFragment': 'Map Fragments', 'Helmet': 'Helmets', 'UniqueFragment': 'Piece', 'Armour': 'Armor', 'Belt': 'Belts', 'Claw': 'Claws', 'Weapon': 'Weapon', 'DivinationCard': 'Divination Card', 'MiscMapItem': 'Misc Map Items', 'Amulet': 'Amulets', 'Ring': 'Rings', 'ThrustingOneHandSword': 'Thrusting One Hand Swords', 'Boots': 'Boots', 'TwoHandSword': 'Two Hand Swords', 'BodyArmour': 'Body Armours', 'Leaguestone': 'Leaguestones'}
