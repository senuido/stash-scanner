# Filter Guide
## General
- **Title**: display name, used in notifications
- **ID**: unique identifier
- **Base ID**: the ID of the filter you want this filter to be based on. Using this will essentialy inherit the criteria from that filter. If theres an overlap, the base is overriden.
  this is useful if you want to create a filter based on an item price from the API or just want to manage related filters more easily.  
  **NOTE**: if you base your filter on a *generated* one, the price that it will get is the effective item price (NOT the actual filter price). this is because generated filters have their prices tweaked by a factor to snipe items.
- **Category**: logical grouping. useful if you want to disable filters by their category.
- **Description**: some text to describe the filter. strictly for convience.
- **Enabled**: specifies if the filter should be active

## Criteria:
- Basic
  - **Name**: item name. you can specify multiple names, for example: `the fiend, the doctor` will match either of those cards
  - **Base**: item base type
  - **Type**: item types, you can choose multiple types (useful for looking items to craft on)
  - **Price**: minimum/maximum price. if Base ID is specified, price can be relative to the base's price. 
         you can use the operators `/`, `*`, `+`,`-` to do so. for example: `+1 ex` or `* 3` or `/ 2`
  - **Buyout**: specifies if the item has a buyout price. Note that if you specify a minimum/maximum price, items without a price will still be matched to allow a bit of flexibility. if you don't want this to happen, just specify buyout to be true.
- Offense/Defense  
_(potential means with 20% quality if possible)_  
  - **DPS**: min/max potential damage per second
  - **PDPS**: min/max potential physical dps
  - **EDPS**: min/max elemental dps
  - **Armour**: min/max potential armour
  - **Evasion**: min/max potential evasion
  - **Energy shield**: min/max potential energy shield
- Sockets
  - **Sockets**: min/max number of sockets
  - **Links**: min/max number of highest length link
- Misc
  - **Item level**: min/max item level
  - **Quality**: min/max item quality
  - **Level**: min/max item level
  - **Experience**: minimum gem experience %
  - **Corrupted**: specifies if item is corrupted
  - **Modifiable**: specifies if you can use currency on the item (not corrupted and not mirrored)
  - **Identified**: specifies if item is identified
  - **Crafted**: specifies if item has crafted mods on it
  - **Enchanted**: specifies if item is enchanted
  - **Mod count**: min/max number of mods. note this isn't very reliable because of 'hybrid' mods which sometimes will be considered as one too many and sometimes wont be accounted for at all. I put this in despite that, because I found it useful for tracking 4 mod jewels, might be useful for other cases.
  - **Stack size**: min/max stack size. useful for essence/cards hunting.

## Filter Groups
Lets you filter item mods by groups. All mod filter groups must be match for an item to be considered matched.
When choosing mods you can either use a predefined mod from the list or add a custom one if you can't find what you're looking for. Custom mods are made of two things:
 - **Expression**: a regular expression describing what to match and what values to extract. Note that the match is case sensitive. You can find a technical reference [here](https://docs.python.org/3.5/library/re.html).
 - **Type**: defines where to match the expression. `Total` means to look in implicit, explicit, crafted and enchanted mods.

For example, if you wanted to find Lion's Roar with 35% more multiplier you could add a custom mod with:
 - **Expression:** `([0-9]+)% more Melee Physical Damage during effect$`
 - **Type:** `Explicit` or `Total`
