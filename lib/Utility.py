import json
import logging
import logging.handlers
import os
import pycurl
import time
import traceback
import uuid
import warnings
from configparser import ConfigParser
from enum import IntEnum
from io import BytesIO
from queue import Queue

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


class AppConfiguration(object):
    CONFIG_FNAME = "cfg\\app.ini"
    section_names = ['Settings']
    defaults = {'league': 'Legacy',
                'request_delay': 1,
                'notification_duration': 4,
                'scan_mode': 'latest'}

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


def tmsg(msg):
    return "{}# {}".format(time.strftime("%H:%M:%S"), msg)


def logexception():
    # logger.exception("Exception information")
    logger.error(traceback.format_exc())

# def logerror(msg):
#     os.makedirs(os.path.dirname(ERROR_FNAME), exist_ok=True)
#     with open(ERROR_FNAME, mode="a") as f:
#         f.write(msg + '\n')

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

config = AppConfiguration()
msgr = Messenger()
