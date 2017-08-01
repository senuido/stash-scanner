import json
import pycurl
import re
import threading
from datetime import datetime, timedelta
from json import JSONEncoder

from lib.Utility import getJsonFromURL, AppException, config, NoIndent, NoIndentEncoder, logexception, msgr, \
    utc_to_local, CompileException

_PRICE_REGEX = re.compile('\s*([0-9]+|[0-9]+\.[0-9]+)\s+([a-z\-]+)')

_OVERRIDE_REGEX = re.compile('\s*([+\-*/]?)\s*(.+)')
_NUMBER_REGEX = re.compile('[0-9]+(?:\.[0-9]+)?$')

INVALID_OVERRIDE = "Invalid override price \'{}\' for {}"
INVALID_OVERRIDE_RATE = "Invalid override rate \'{}\' = {} for {}. Rate must be a positive number"
INVALID_PRICE = "Invalid price {}"

class CurrencyManager:
    CURRENCY_FNAME = "cfg\\currency.json"
    CURRENCY_API = ["http://poeninja.azureedge.net/api/Data/GetCurrencyOverview?league={}",
                    "http://poeninja.azureedge.net/api/Data/GetFragmentOverview?league={}"]
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
    UPDATE_INTERVAL = 10  # minutes

    def __init__(self):
        self.init()

    def init(self):
        self.rates = {}
        self.whisper = CurrencyManager.CURRENCY_WHISPER_BASE  # short to whisper message name mapping
        self.shorts = {curr: [short] for curr, short in self.whisper.items()}
        self.overrides = {}

        self.cshorts = {}  # short to full name mapping
        self.crates = {}  # rates with overrides
        self.compile_lock = threading.Lock()

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
            last_update = data.get('last_update') or ''

            try:
                self.last_update = datetime.strptime(last_update, '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                self.last_update = datetime.utcnow() - timedelta(minutes=self.UPDATE_INTERVAL)

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
            'whisper': self.whisper,
            'last_update': self.last_update
        }

        with open(CurrencyManager.CURRENCY_FNAME, "w", encoding="utf-8", errors="replace") as f:
            f.write(json.dumps(data, indent=4, separators=(',', ': '), sort_keys=True, cls=CurrencyEncoder))

    def compile(self, shorts=None, rates=None, overrides=None, last_update=None):
        with self.compile_lock:
            if rates is None:
                rates = self.rates
            if shorts is None:
                shorts = self.shorts
            if overrides is None:
                overrides = self.overrides

            tcm = CurrencyManager()
            tcm._compile(rates, shorts, overrides)

            self.shorts = shorts
            self.rates = rates
            self.overrides = overrides
            self.cshorts = tcm.cshorts
            self.crates = tcm.crates

            if last_update:
                self.last_update = last_update
            self.save()
            self.initialized = True

            msgr.send_object(CurrencyInfo())


    @property
    def needUpdate(self):
        return not self.last_update or (datetime.utcnow() - self.last_update) >= timedelta(minutes=self.UPDATE_INTERVAL)

    def update(self, force_update=False):
        if not force_update and not self.needUpdate:
            return

        # print('updating currency..')

        try:
            shorts = {}
            rates = {}
            for url in CurrencyManager.CURRENCY_API:
                data = getJsonFromURL(url.format(config.league))

                if data is None:
                    raise AppException("Currency update failed. bad response from server.")

                shorts.update({currency['name']: currency['shorthands'] for currency in data["currencyDetails"]})
                rates.update({currency['currencyTypeName']: float(currency['chaosEquivalent']) for currency in data["lines"]})

            cur_shorts = dict(self.shorts)
            for curr in shorts:
                shorts[curr] = list(set(cur_shorts.get(curr, []) + shorts[curr]))

            # can use update if we want to keep information from past updates, more robust if server returns less data
            # dict(self.rates).update(rates)

            self.compile(shorts, rates, last_update=datetime.utcnow())
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
        if short in self.cshorts:
            currency = self.cshorts[short]
            if currency == "Chaos Orb":
                return amount
            if currency in self.crates:
                return amount * self.crates[self.cshorts[short]]
        return 0

    def isPriceValid(self, price_str):
        price = CurrencyManager.priceFromString(price_str)
        if price is None:
            return False
        return price[1] in self.cshorts

    def toDisplayPrice(self, rate):
        ex_val = self.convert(1, 'exalted')
        if 0 < ex_val <= rate:
            rate = round(rate / ex_val, 2)
            if rate == int(rate): rate = int(rate)
            price = '{} ex'.format(rate)
        else:
            price = '{:.0f}c'.format(rate)
        return price

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

    def _apply_override(self, key, val, overrides, path=None):
        if path is None:
            path = []
        path.append(key)

        # if not self.isPriceValid(str(val)):
        if not self.isOverridePriceValid(str(val)):
            raise AppException(INVALID_OVERRIDE.format(val, key))
        opr, price = self.overridePriceFromString(str(val))

        if opr not in ('', '*', '/'):
            amount, short = self.priceFromString(price)
            tkey = self.cshorts[short]
            if tkey in overrides:
                self._apply_override(tkey, overrides.pop(tkey), overrides, path)

            if tkey in path and tkey != key:
                raise AppException("Overrides contain a circular reference in path: {}".format(path))

        # rate = self.convert(float(amount), short)
        rate = self.compilePrice(val, self.crates.get(key))
        if rate <= 0:
            rate = 0
            # raise AppException(INVALID_OVERRIDE_RATE.format(val, rate, key))
        self.crates[key] = rate
        del path[-1]

    def _compile(self, rates, shorts, overrides):
        cshorts = {}

        for curr in shorts:
            for short in shorts[curr]:
                cshorts[short] = curr

        overrides = dict(overrides)
        self.cshorts = cshorts
        self.crates = dict(rates)

        try:
            while True:
                self._apply_override(*overrides.popitem(), overrides)
        except AppException:
            raise
        except KeyError:
            pass

    @staticmethod
    def priceFromString(price):
        match = _PRICE_REGEX.match(price.lower())
        if match is not None:
            return match.groups()
        return None

    @staticmethod
    def overridePriceFromString(override_price):
        match = _OVERRIDE_REGEX.match(str(override_price))
        if match is not None:
            # opr, price = match.groups()
            return match.groups()
        return None

    def isOverridePriceValid(self, override_price):
        match = CurrencyManager.overridePriceFromString(override_price)
        if match is not None:
            opr, price = match
            if opr in ('*', '/'):
                return _NUMBER_REGEX.match(price) is not None and float(price) > 0
            else:
                return self.isPriceValid(price)
        return False

    @staticmethod
    def isPriceRelative(override_price):
        opr, price = _OVERRIDE_REGEX.match(str(override_price)).groups()
        return opr != ''

    def compilePrice(self, override_price, base_price=None):
        opr, price = _OVERRIDE_REGEX.match(str(override_price)).groups()
        new_price = 0

        if opr != '' and base_price is None:
            raise CompileException('Price \'{}\' is relative but base price is missing.'.format(override_price))

        # factor
        if opr in ('', '+', '-'):
            amount, short = CurrencyManager.priceFromString(price)
            val = self.convert(float(amount), short)
        else:
            val = float(price)

        if opr == '':
            new_price = val
        elif opr == '+':
            new_price = base_price + val
        elif opr == '-':
            new_price = base_price - val
        elif opr == '*':
            new_price = base_price * val
        elif opr == '/':
            new_price = base_price / val

        return new_price

    @classmethod
    def clearCache(cls):
        cm.rates = {}
        cm.last_update = None
        cm.save()

class CurrencyInfo:
    def __init__(self):
        if cm.initialized:
            self.rates = dict(cm.crates)
            self.last_update = utc_to_local(cm.last_update) if cm.last_update else None
        else:
            self.rates = None
            self.last_update = None

class CurrencyEncoder(NoIndentEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

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

