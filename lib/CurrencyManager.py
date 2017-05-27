import json
import pycurl

from lib.Utility import getJsonFromURL, AppException, config


class CurrencyManager:
    CURRENCY_FNAME = "cfg\\currency.json"
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
        'mir': 'mirror',
        # 'other': 'other'
    }

    def __init__(self):
        self.shorts = {}    # short to full name mapping
        self.rates = {}
        self.whisper = CurrencyManager.CURRENCY_DISPLAY_BASE    # short to whisper message name mapping
        self.overrides = {}
        self.initialized = False

        self.load()

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
            self.rates.update(self.overrides)

            self.initialized = True
        except FileNotFoundError:
            pass

    def save(self):
        data = {}
        data['overrides'] = self.overrides
        data['rates'] = self.rates

        with open(CurrencyManager.CURRENCY_FNAME, "w", encoding="utf-8", errors="replace") as f:
            json.dump(data, f, indent=4, separators=(',', ': '))

    def update(self):
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
                #if 'value' in currencies[currency]:
                for short in currencies[currency]['shorts']:
                    shorts[short] = currency

            whisper = {}
            for currency in CurrencyManager.CURRENCY_DISPLAY_BASE:
                if currency not in shorts:
                    print("{} not in shorts".format(currency))
                    whisper[currency] = CurrencyManager.CURRENCY_DISPLAY_BASE[currency]
                else:
                    for short in currencies[shorts[currency]]['shorts']:
                        whisper[short] = CurrencyManager.CURRENCY_DISPLAY_BASE[currency]

            self.rates = rates
            self.shorts = shorts
            self.whisper = whisper

            self.save()
            self.rates.update(self.overrides)

            self.initialized = True
        except pycurl.error as e:
            raise AppException("Currency update failed. Connection error: {}".format(e))
        except AppException:
            raise
        except (KeyError, ValueError) as e:
            raise AppException("Currency update failed. Parsing error: {}".format(e))
        except Exception as e:
            raise AppException("Currency update failed. Unexpected error: {}".format(e))

cm = CurrencyManager()

if __name__ == "__main__":
    cm.update()

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
