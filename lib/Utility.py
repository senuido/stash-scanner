import json
import os
import pycurl
import time
from configparser import ConfigParser
from io import BytesIO


class AppException(Exception):
    pass


class AppConfiguration(object):
    CONFIG_FNAME = "cfg\\app.cfg"
    section_names = ['Settings']
    defaults = {'league': 'Legacy',
                'request_delay': 0.5,
                'request_ahead_delay': 1,
                'notification_duration': 4}

    def __init__(self):
        parser = ConfigParser()
        #parser.optionxform = str  # make option names case sensitive
        found = parser.read(AppConfiguration.CONFIG_FNAME)

        if not found or AppConfiguration.section_names[0] not in parser.sections():
            parser[AppConfiguration.section_names[0]] = AppConfiguration.defaults
        else:
            values = dict(AppConfiguration.defaults)
            values.update(parser[AppConfiguration.section_names[0]])
            parser[AppConfiguration.section_names[0]] = values

        for section in parser.sections():
            if section not in AppConfiguration.section_names:
                parser.remove_section(section)

        os.makedirs(os.path.dirname(AppConfiguration.CONFIG_FNAME), exist_ok=True)
        with open(AppConfiguration.CONFIG_FNAME, mode="w") as f:
            parser.write(f)

        for name in AppConfiguration.section_names:
            self.__dict__.update(parser.items(name))

config = AppConfiguration()

def getJsonFromURL(url, handle=None, max_attempts=1):
    if not handle:
        handle = pycurl.Curl()

    buffer = BytesIO()
    handle.setopt(handle.URL, url)
    # handle.setopt(handle.VERBOSE, 1)
    handle.setopt(handle.ENCODING, 'gzip, deflate')
    handle.setopt(handle.WRITEFUNCTION, buffer.write)

    attempts = 0

    while attempts < max_attempts:
        if attempts > 0:
            time.sleep(2)

        handle.perform()
        if handle.getinfo(handle.RESPONSE_CODE) == 200:
            return json.loads(buffer.getvalue().decode())

        attempts += 1
        print(tmsg("HTTP Code: {} while trying to retrieve URL: {}".format(handle.getinfo(handle.RESPONSE_CODE), url)))

    return None


def str2bool(val):
    if val.lower() in ("true", "t", "yes", "y", "1"): return True
    if val.lower() in ("false", "f", "no", "n", "0"): return False
    raise ValueError


def tmsg(msg):
    return "{}# {}".format(time.strftime("%H:%M:%S"), msg)