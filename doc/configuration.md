# Configuration Guide
You can configure almost everything just using the bottom pane in the main window and the filter editor.  
It is important you take the time to understand and configure the tool properly if you want to get the most out of it.  
Make sure to Apply/Save once you're done making changes. If the scanner is active, changes will be applied to it, so don't worry about restarting it. 

## General
- **League:** the league you're interested in
- **Request delay:** minimum time delay between requests to PoE stash API, tweak this if you're getting throttled
- **Scan mode**
  - Latest: start scanning from the latest data. Use this unless you're interested in historical data.
  - Continue: resume scanning from the last stopping point. if there is none, starts from the latest data
- **Growl notifications:** turn on/off notifications
- **Notification duration**
- **Copy message to clipboard**

## Prices
Here you can view the item prices retrieved from the API.

For every item retrieved from the API, a filter is generated. To allow you to tweak these prices, you can use _overrides_.  
Overrides follow the same format as prices. For example, to change an item's price to be 20 chaos, just put in `20 chaos`.  
Same as prices for filters, overrides can be relative to the original price. For example: `+1 ex` or `* 3` or `/ 2`

  - **Item price threshold:** think of this as the minimum value of items you're interested in. *Generated* filters for items with effective price below this threshold will be disabled.
  - **Default price override:** default item price override. if none is specified, this is used.
  - **Default filter override:** default filter price override. if none is specified, this is used. By setting this to `* 0.8` you're telling the app you want to be notified when an item is posted at 80% of its API price.
  - Table  
    - **Item Price:** item price as it was retrieved from the API
    - **Override:** override for item price.
    - **Filter Price:** the effective item price (which means item price after override is applied).
    - **Filter Override:** override for generated filter price, if none is specified the default override is used.
    - **Effective Filter Price:** filter price after override is applied
    - **Filter State Override:** if a specific filter is disabled because it is under the threshold and you want to enable it anyway, use this override.
    same goes for specific filters you want disabled even though they're above the threshold

## Currency
Here you can view and tweak currency rates to use:
  - **Rate:** currency rate as retrieved from API
  - **Override:** override to modify the rate, leave empty 
  - **Effective rate:** actual currency chaos rate (rate after override is applied)

Note the API might not provide a rate for extremely rare currency such as mirrors/eternal orbs. This can create false alerts because their rate will default to 0.
To avoid that, provide an estimated price using an override, such as `50 ex` or whatever you see fit.

## Filters
#### Configuration
Custom filters are configured using the filter editor. for specific information on filters, view the [filter guide](filter.md).

#### Generated filters
These filters are read-only and cannot be removed, but they can be disabled:
* **Specific:** you can control individual filters if you use set their state override in the *Prices tab*. this will force a specific filter to be disabled/enabled, ignoring other configurations.

* **By price:** Generally *generated* filters above the threshold will be active.  By settings this to a high enough value, you can disable all generated filters if you wish. You can set it in the *Prices tab*.

* **By category:** You can disable filters by categories but it can't be done using the UI yet.  
If you want to do that you need to open up *filters.config.json* and fill *disabled_categories*. Make sure the application is closed before you do. Example how this looks like:
```
{
    "default_fprice_override": "* 0.7",
    "default_price_override": "* 1",
    "disabled_categories": [
        "divinationcards",
        "essence",
        "prophecy",
        "uniqueaccessory",
        "uniquearmour",
        "uniqueflask",
        "uniquejewel",
        "uniqueweapon"
    ],
    "filter_price_overrides": {},
    "filter_state_overrides": {},
    "price_overrides": {},
    "price_threshold": "10 chaos"
}
```

## File structure
Under `cfg` directory:
- `app.ini`: contains general setting and preferences
- `filters.json`: contains user item filters information
- `filters.config.json`: contains mostly configuration for generated filters. price threshold, item price overrides, price overrides and disabled categories
- `currency.json`: contains currency information. currency names, rates, rates overrides, etc.
