import json
import pycurl

import re

from lib.Utility import getJsonFromURL, AppException, config

_PRICE_REGEX = re.compile('\s*([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
INVALID_OVERRIDE = "Invalid override price \'{}\' for {}"
INVALID_OVERRIDE_RATE = "Invalid override rate \'{}\' = {} for {}. Rate must be a positive number"
INVALID_PRICE = "Invalid price {}"

class CurrencyManager:
    CURRENCY_FNAME = "tmp\\currency.json"
    CURRENCY_CFG_FNAME = "cfg\\currency-config.json"
    CURRENCY_API = "http://poeninja.azureedge.net/api/Data/GetCurrencyOverview?league={}"

    CURRENCY_DISPLAY_BASE = {
        'alt': 'alternation',
        'fuse': 'fusing',
        'alch': 'alchemy',
        'exa': 'exalted',
        'chrom': 'chromatic',
        'jew': 'jewellers',
        'chance': 'chance',
        'scour': 'scouring',
        'chaos': 'chaos',
        'blessed': 'blessed',
        'regret': 'regret',
        'regal': 'regal',
        'divine': 'divine',
        'vaal': 'vaal',
        'chisel': 'chisel',
        'gcp': 'gcp',
        'eternal': 'eternal',
        'mir': 'mirror'
    }

    def __init__(self):
        self.shorts = {}    # short to full name mapping
        self.rates = {}
        self.whisper = CurrencyManager.CURRENCY_DISPLAY_BASE    # short to whisper message name mapping
        self.overrides = {}
        self.initialized = False

    @classmethod
    def fromData(cls, shorts, rates, whisper, overrides):
        ncm = cls()
        ncm.shorts = shorts
        ncm.rates = rates
        ncm.whisper = whisper
        ncm.overrides = overrides

        return ncm

    def convert(self, amount, short):
        if short in self.shorts:
            currency = self.shorts[short]
            if currency == "Chaos Orb": return amount  # HARDCODED rather than use an override
            if currency in self.rates:
                return amount * self.rates[self.shorts[short]]
        return 0

    def load(self):
        try:
            with open(CurrencyManager.CURRENCY_FNAME, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            self.overrides = data['overrides']
            self.rates = data['rates']
            self.shorts = data['shorts']
            self.whisper = data['whisper']

            self.apply_overrides()

            self.initialized = True
        except FileNotFoundError:
            pass

    def apply_override(self, key, val, overrides, path=None):
        if path is None:
            path = []
        path.append(key)

        price = CurrencyManager.priceFromString(str(val))
        if price is None:
            raise AppException(INVALID_OVERRIDE.format(val, key))

        amount, short = price
        if short not in self.shorts:
            raise AppException(INVALID_OVERRIDE.format(val, key))

        tkey = self.shorts[short]
        if tkey in overrides:
            self.apply_override(tkey, overrides.pop(tkey), overrides, path)

        if tkey in path and tkey != key:
            raise AppException("Overrides contain a circular reference in path: {}".format(path))

        rate = self.convert(float(amount), short)
        if rate <= 0:
            raise AppException(INVALID_OVERRIDE_RATE.format(val, rate, key))
        self.rates[key] = self.convert(float(amount), short)
        del path[-1]

    def apply_overrides(self):
        overrides = dict(self.overrides)

        try:
            while True:
                self.apply_override(*overrides.popitem(), overrides)
        except AppException:
            raise
        except KeyError:
            pass

    def save(self):
        data = {}
        data['overrides'] = self.overrides
        data['rates'] = self.rates
        data['shorts'] = self.shorts
        data['whisper'] = self.whisper

        with open(CurrencyManager.CURRENCY_FNAME, "w", encoding="utf-8", errors="replace") as f:
            json.dump(data, f, indent=4, separators=(',', ': '), sort_keys=True)

    @staticmethod
    def priceFromString(price):
        match = _PRICE_REGEX.match(price.lower())
        if match is not None:
            return match.groups()
        return None

    def isPriceValid(self, price_str):
        price = CurrencyManager.priceFromString(price_str)
        if price is None:
            return False
        return price[1] in self.shorts


    @staticmethod
    def update():
        global cm
        ncm = CurrencyManager.fromAPI()
        ncm.save()
        ncm.apply_overrides()
        ncm.initialized = True
        cm = ncm

    @staticmethod
    def fromAPI():
        url = CurrencyManager.CURRENCY_API.format(config.league)

        try:
            data = getJsonFromURL(url)

            if data is None:
                raise AppException("Currency update failed. bad response from server.")

            currencies = {}
            for currency in data["currencyDetails"]:
                currencies[currency['name']] = {}
                currencies[currency['name']]['id'] = currency['id']
                currencies[currency['name']]['shorts'] = currency['shorthands']

            for currency in data["lines"]:
                name = currency['currencyTypeName']
                val = float(currency['chaosEquivalent'])
                if val > 0:  # sanity check
                    currencies[name]['value'] = val

            # Create our shortcut dictionaries
            rates = {}
            for currency in currencies:
                if 'value' in currencies[currency]:
                    rates[currency] = currencies[currency]['value']

            shorts = {}
            for currency in currencies:
                # if 'value' in currencies[currency]:
                for short in currencies[currency]['shorts']:
                    shorts[short] = currency

            whisper = {}
            for currency in CurrencyManager.CURRENCY_DISPLAY_BASE:
                if currency not in shorts:
                    # print("{} not in shorts".format(currency))
                    whisper[currency] = CurrencyManager.CURRENCY_DISPLAY_BASE[currency]
                else:
                    for short in currencies[shorts[currency]]['shorts']:
                        whisper[short] = CurrencyManager.CURRENCY_DISPLAY_BASE[currency]

            ncm = CurrencyManager.fromData(shorts, rates, whisper, cm.overrides)

            # test overrides work, kinda hacky, could just add another dictionary for original rates
            org_rates = dict(rates)
            ncm.apply_overrides()
            ncm.rates = org_rates
        except pycurl.error as e:
            raise AppException("Currency update failed. Connection error: {}".format(e))
        except AppException:
            raise
        except (KeyError, ValueError) as e:
            raise AppException("Currency update failed. Parsing error: {}".format(e))
        except Exception as e:
            raise AppException("Currency update failed. Unexpected error: {}".format(e))
        else:
            return ncm

cm = CurrencyManager()

if __name__ == "__main__":
    CurrencyManager.CURRENCY_FNAME = "..\\" + CurrencyManager.CURRENCY_FNAME

    try:
        cm.load()
    except AppException as e:
        print(e)

    try:
        cm.update()
    except AppException as e:
        print(e)

    print("Rates:")

    for currency in cm.rates:
        print("{}: {}".format(currency, cm.rates[currency]))

    print('\n'*3 + "Shorts:")

    d = {}
    for short, name in cm.shorts.items():
        d.setdefault(name, []).append(short)

    for name in d:
        print("{}: {}".format(name, d[name]))

    print('\n'*3 + "Whisper names:")

    d = {}
    for short, name in cm.whisper.items():
        d.setdefault(name, []).append(short)

    for name in d:
        print("{}: {}".format(name, d[name]))

    print("0.8 divine = {} chaos".format(cm.convert(0.8, 'div')))
