import json
import pycurl

import re
from datetime import datetime

from lib.Utility import getJsonFromURL, AppException, config, NoIndent, NoIndentEncoder, logexception, msgr

_PRICE_REGEX = re.compile('\s*([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')
INVALID_OVERRIDE = "Invalid override price \'{}\' for {}"
INVALID_OVERRIDE_RATE = "Invalid override rate \'{}\' = {} for {}. Rate must be a positive number"
INVALID_PRICE = "Invalid price {}"

class CurrencyManager:
    CURRENCY_FNAME = "cfg\\currency.json"
    CURRENCY_API = "http://poeninja.azureedge.net/api/Data/GetCurrencyOverview?league={}"

    CURRENCY_WHISPER_BASE = {
        "Apprentice Cartographer's Sextant": 'apprentice sextant',
        "Armourer's Scrap": "armourer's",
        "Blacksmith's Whetstone": 'whetstone',
        "Blessed Orb": 'blessed',
        "Cartographer's Chisel": 'chisel',
        "Chromatic Orb": 'chromatic',
        "Divine Orb": 'divine',
        "Exalted Orb": 'exalted',
        "Gemcutter's Prism": 'gcp',
        "Glassblower's Bauble": 'bauble',
        "Jeweller's Orb": 'jewellers',
        "Journeyman Cartographer's Sextant": 'journeyman sextant',
        "Master Cartographer's Sextant": 'master sextant',
        "Orb of Alchemy": 'alchemy',
        "Orb of Alteration": 'alternation',
        "Orb of Augmentation": 'augmentation',
        "Orb of Chance": 'chance',
        "Orb of Fusing": 'fusing',
        "Orb of Regret": 'regret',
        "Orb of Scouring": 'scouring',
        "Orb of Transmutation": 'transmutation',
        "Chaos Orb": 'chaos',
        "Portal Scroll": 'portal',
        "Regal Orb": 'regal',
        "Silver Coin": 'silver',
        "Vaal Orb": 'vaal',
        "Eternal Orb": 'eternal',
        "Mirror of Kalandra": 'mirror'
    }

    def __init__(self):
        self.rates = {}
        self.whisper = CurrencyManager.CURRENCY_WHISPER_BASE    # short to whisper message name mapping
        self.shorts = {curr: [short] for curr, short in self.whisper.items()}
        self.overrides = {}

        self.cshorts = {}   # short to full name mapping
        self.crates = {}    # rates with overrides

        self.last_update = None

        self.initialized = False

    def load(self):
        try:
            with open(CurrencyManager.CURRENCY_FNAME, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            self.overrides = data.get('overrides', {})
            self.rates = data.get('rates', {})
            self.shorts = data.get('shorts', self.shorts)
            self.whisper = data.get('whisper', self.whisper)

            for curr in self.shorts:
                self.shorts[curr] = list(set([short.lower() for short in self.shorts[curr]]))

            self.compile()
        except FileNotFoundError:
            self.save()

    def save(self):
        data = {
            'overrides': self.overrides,
            'rates': self.rates,
            'shorts': {k: NoIndent(v) for k, v in self.shorts.items()},
            'whisper': self.whisper
        }

        with open(CurrencyManager.CURRENCY_FNAME, "w", encoding="utf-8", errors="replace") as f:
            f.write(json.dumps(data, indent=4, separators=(',', ': '), sort_keys=True, cls=NoIndentEncoder))

    def compile(self, shorts=None, rates=None):
        if rates is None:
            rates = self.rates
        if shorts is None:
            shorts = self.shorts

        cshorts = {}

        for curr in shorts:
            for short in shorts[curr]:
                cshorts[short] = curr

        crates = CurrencyManager.apply_overrides(cshorts, rates, self.overrides)

        self.shorts = shorts
        self.rates = rates
        self.cshorts = cshorts
        self.crates = crates
        self.last_update = datetime.now()
        self.save()
        self.initialized = True

        msgr.send_object(CurrencyInfo())

    def update(self):
        url = CurrencyManager.CURRENCY_API.format(config.league)

        try:
            data = getJsonFromURL(url)

            if data is None:
                raise AppException("Currency update failed. bad response from server.")

            shorts = {currency['name']: currency['shorthands'] for currency in data["currencyDetails"]}
            rates = {currency['currencyTypeName']: float(currency['chaosEquivalent']) for currency in data["lines"]}

            for curr in shorts:
                shorts[curr] = list(set(self.shorts.get(curr, []) + shorts[curr]))

            # can use update if we want to keep information from past updates, more robust if server returns less data
            # dict(self.rates).update(rates)

            self.compile(shorts, rates)
        except pycurl.error as e:
            raise AppException("Currency update failed. Connection error: {}".format(e))
        except AppException:
            raise
        except (KeyError, ValueError) as e:
            raise AppException("Currency update failed. Parsing error: {}".format(e))
        except Exception as e:
            logexception()
            raise AppException("Currency update failed. Unexpected error: {}".format(e))

    def convert(self, amount, short):
        return CurrencyManager._convert(amount, short, self.cshorts, self.crates)

    def isPriceValid(self, price_str):
        price = CurrencyManager.priceFromString(price_str)
        if price is None:
            return False
        return price[1] in self.cshorts

    def toWhisper(self, short):
        try:
            return self.whisper[self.cshorts[short]]
        except KeyError:
            return short

    def toFull(self, short):
        try:
            return self.cshorts[short]
        except KeyError:
            return short

    @staticmethod
    def _convert(amount, short, cshorts, rates):
        if short in cshorts:
            currency = cshorts[short]
            if currency == "Chaos Orb":
                return amount
            if currency in rates:
                return amount * rates[cshorts[short]]
        return 0

    @staticmethod
    def apply_override(key, val, overrides, cshorts, rates, path=None):
        if path is None:
            path = []
        path.append(key)

        price = CurrencyManager.priceFromString(str(val))
        if price is None:
            raise AppException(INVALID_OVERRIDE.format(val, key))

        amount, short = price
        if short not in cshorts:
            raise AppException(INVALID_OVERRIDE.format(val, key))

        tkey = cshorts[short]
        if tkey in overrides:
            CurrencyManager.apply_override(tkey, overrides.pop(tkey), overrides, cshorts, rates, path)

        if tkey in path and tkey != key:
            raise AppException("Overrides contain a circular reference in path: {}".format(path))

        rate = CurrencyManager._convert(float(amount), short, cshorts, rates)
        if rate <= 0:
            raise AppException(INVALID_OVERRIDE_RATE.format(val, rate, key))
        rates[key] = rate
        del path[-1]

    @staticmethod
    def apply_overrides(cshorts, rates, overrides):
        overrides = dict(overrides)
        rates = dict(rates)

        try:
            while True:
                CurrencyManager.apply_override(*overrides.popitem(), overrides, cshorts, rates)
        except AppException:
            raise
        except KeyError:
            return rates

    @staticmethod
    def priceFromString(price):
        match = _PRICE_REGEX.match(price.lower())
        if match is not None:
            return match.groups()
        return None


class CurrencyInfo:
    def __init__(self):
        if cm.initialized:
            self.rates = dict(cm.crates)
            self.last_update = cm.last_update
        else:
            self.rates = None
            self.last_update = None


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
