import json
import logging
import logging.handlers
import os
import pycurl
import re
import time
import traceback
import uuid
import warnings
from configparser import ConfigParser
from enum import IntEnum
from io import BytesIO
from queue import Queue
from urllib.parse import urlparse, quote
from datetime import timezone

warnings.filterwarnings('ignore', message='.*parallel loops cannot be nested below threads.*', category=UserWarning)

os.makedirs('log', exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s# %(name)-15s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

fh = logging.handlers.RotatingFileHandler('log\\app.log', encoding='utf-8', maxBytes=10*1024*1024, backupCount=1)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.WARN)

root_logger.addHandler(fh)
root_logger.addHandler(ch)
logger = root_logger
# logger = logging.getLogger('scanner') #logging.getLogger(__name__)

RE_COMPILED_TYPE = type(re.compile(''))

class MsgType(IntEnum):
    ScanStopped = 0
    UpdateID = 1
    Text = 10
    Object = 11
    Custom = 100


class Messenger:
    def __init__(self):
        self.msg_queue = Queue()
        # self.log_level = logging.INFO

    def send_tmsg(self, msg, log_level=logging.NOTSET, tag=None):
        self.send_msg(msg, log_level, timed=True, tag=tag)

    def send_msg(self, msg, log_level=logging.NOTSET, timed=False, tag=None):
        if log_level == logging.NOTSET:
            logger.log(logging.INFO, msg)
        else:
            logger.log(log_level, msg)
        # if self.log_level >= log_level:
        if timed:
            msg = tmsg(msg)
        self.msg_queue.put((MsgType.Text, log_level, msg, tag))

    def send_stopped(self):
        self.msg_queue.put((MsgType.ScanStopped,))

    def send_update_id(self, id):
        self.msg_queue.put((MsgType.UpdateID, id))

    def send_object(self, obj):
        self.msg_queue.put((MsgType.Object, obj))


class AppException(Exception):
    pass

# used to propogate reasons for compilation failure
class CompileException(AppException):
    pass

class AppConfiguration:
    CONFIG_FNAME = "cfg\\app.ini"
    section_name = 'Settings'
    # section_names = ['Settings']

    def __init__(self, load=True):

        self.league = None
        self.request_delay = None
        self.budget = None
        self.notify = None
        self.notify_copy_msg = None
        self.notify_play_sound = None
        self.notification_duration = None
        self.scan_mode = None

        if load:
            self.load()

        # parser = ConfigParser()
        # #parser.optionxform = str  # make option names case sensitive
        # found = parser.read(AppConfiguration.CONFIG_FNAME)
        #
        # if not found or AppConfiguration.section_names[0] not in parser.sections():
        #     parser[AppConfiguration.section_names[0]] = AppConfiguration.defaults
        # else:
        #     values = dict(AppConfiguration.defaults)
        #     values.update(parser[AppConfiguration.section_names[0]])
        #     parser[AppConfiguration.section_names[0]] = values
        #
        # for section in parser.sections():
        #     if section not in AppConfiguration.section_names:
        #         parser.remove_section(section)
        #
        # os.makedirs(os.path.dirname(AppConfiguration.CONFIG_FNAME), exist_ok=True)
        # with open(AppConfiguration.CONFIG_FNAME, mode="w") as f:
        #     parser.write(f)
        #
        # for name in AppConfiguration.section_names:
        #     self.__dict__.update(parser.items(name))

    def load(self):
        parser = ConfigParser()
        found = parser.read(AppConfiguration.CONFIG_FNAME)

        settings = {}
        if found and self.section_name in parser.sections():
            settings = parser[self.section_name]

        try:
            self.request_delay = float(settings['request_delay'])
        except Exception:
            self.request_delay = 1

        try:
            self.notify = str2bool(settings['notify'])
        except Exception:
            self.notify = True

        try:
            self.notify_copy_msg = str2bool(settings['notify_copy_msg'])
        except Exception:
            self.notify_copy_msg = True

        try:
            self.notify_play_sound = str2bool(settings['notify_play_sound'])
        except Exception:
            self.notify_play_sound = True

        try:
            self.notification_duration = float(settings['notification_duration'])
        except Exception:
            self.notification_duration = 4

        # TODO: validate
        self.league = settings.get('league', 'Standard')
        self.scan_mode = settings.get('scan_mode', 'Latest')

        self.save()

    def update(self, cfg):
        if not isinstance(cfg, AppConfiguration):
            raise TypeError('cfg must be of type AppConfiguration')

        self.league = cfg.league
        self.notify = cfg.notify
        self.notify_copy_msg = cfg.notify_copy_msg
        self.notify_play_sound = cfg.notify_play_sound
        self.notification_duration = cfg.notification_duration
        self.request_delay = cfg.request_delay
        self.scan_mode = cfg.scan_mode

    def save(self):
        parser = ConfigParser()
        parser.add_section(self.section_name)

        values = {
            'league': self.league,
            'request_delay': self.request_delay,
            'notify': self.notify,
            'notify_copy_msg': self.notify_copy_msg,
            'notify_play_sound': self.notify_play_sound,
            'notification_duration': self.notification_duration,
            'scan_mode': self.scan_mode
        }

        parser[self.section_name] = values

        os.makedirs(os.path.dirname(AppConfiguration.CONFIG_FNAME), exist_ok=True)
        with open(AppConfiguration.CONFIG_FNAME, mode="w") as f:
            parser.write(f)

def getJsonFromURL(url, handle=None, max_attempts=1):
    if not handle:
        handle = pycurl.Curl()

    url = quote(url, safe=':/?=')

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
        msgr.send_tmsg("HTTP Code: {} while trying to retrieve URL: {}"
                       .format(handle.getinfo(handle.RESPONSE_CODE), url), logging.WARN)

    return None


def getDataFromUrl(url, callback, max_attempts=1):
    c = pycurl.Curl()
    buffer = BytesIO()
    c.setopt(c.URL, url)
    c.setopt(c.TIMEOUT, 5)
    # c.setopt(c.VERBOSE, 1)
    c.setopt(c.ENCODING, 'gzip, deflate')
    c.setopt(c.WRITEFUNCTION, buffer.write)
    c.setopt(c.FOLLOWLOCATION, True)

    retrieved = False
    attempts = 0
    while attempts < max_attempts and not retrieved:
        try:
            c.perform()
            if c.getinfo(c.RESPONSE_CODE) == 200 and c.getinfo(c.CONTENT_LENGTH_DOWNLOAD):
                data = buffer
                callback(url, data)
                retrieved = True

            # print('Data Length: {}'.format(len(buffer.getbuffer())))
        except pycurl.error as e:
            pass

        attempts += 1

    if not retrieved:
        callback(url, None)
    c.close()


def str2bool(val):
    if val.lower() in ("true", "t", "yes", "y", "1"): return True
    if val.lower() in ("false", "f", "no", "n", "0"): return False
    raise ValueError


def round_up(num):
    if int(num) == num:
        return int(num)
    return int(num) + 1

def round_down(num):
    if int(num) == num:
        return int(num)
    return int(num)

def dround(num, ndigits=2):
    num = round(num, ndigits)
    if int(num) == num:
        return int(num)
    return num

def tmsg(msg):
    return "{}# {}".format(time.strftime("%H:%M:%S"), msg)

def getBaseUrl(url):
    # parsed = urlparse(url)
    # return urljoin('{}://'.format(parsed.scheme), parsed.netloc)
    return urlparse(url).geturl()

def isAbsoluteUrl(url):
    return bool(urlparse(url).netloc)

def logexception():
    # logger.exception("Exception information")
    logger.error(traceback.format_exc())

# def logerror(msg):
#     os.makedirs(os.path.dirname(ERROR_FNAME), exist_ok=True)
#     with open(ERROR_FNAME, mode="a") as f:
#         f.write(msg + '\n')

def get_verror_msg(verror, data=None):
    pathMsg = ""
    for i, p in enumerate(verror.path):
        if isinstance(p, int):
            if i == 0:
                pathMsg += "filter #{}".format(p + 1)
                if data is not None:
                    filter_name = data[p].get("title", "")
                    if filter_name:
                        pathMsg += " ({})".format(filter_name)
            elif verror.path[i - 1] == "mods":
                pathMsg += " > mod #{}".format(p + 1)
            elif verror.path[i - 1] == "values":
                pathMsg += " > value #{}".format(p + 1)
        else:
            pathMsg += " > {}".format(p)

    if pathMsg:
        return "{} >>>> {}".format(verror.message, pathMsg)

    return verror.message

class NoIndent(object):
    def __init__(self, value):
        self.value = value


class NoIndentEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super(NoIndentEncoder, self).__init__(*args, **kwargs)
        self.kwargs = dict(kwargs)
        del self.kwargs['indent']
        self._replacement_map = {}

    def default(self, o):
        if isinstance(o, NoIndent):
            key = uuid.uuid4().hex
            self._replacement_map[key] = json.dumps(o.value, **self.kwargs)
            return "@@{}@@".format((key,))
        else:
            return super(NoIndentEncoder, self).default(o)

    def encode(self, o):
        result = super(NoIndentEncoder, self).encode(o)
        for k, v in self._replacement_map.items():
            result = result.replace('"@@{}@@"'.format((k,)), v)
        return result

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

def namify(text):
    """
    :param text: 
    :return: text with a space before every capital letter if no capital or space precedes it 
    """
    return re.sub('(?<![A-Z\s])(?<!^)([A-Z])', r' \1', text)

def normalize_id(text):
    return str(text).replace(' ', '')

config = AppConfiguration()
msgr = Messenger()


class ConfidenceLevel(IntEnum):
    Low = 1
    Medium = 5
    High = 10
    VeryHigh = 15