import os
import pycurl
import time
import traceback
import winsound
from enum import IntEnum
from threading import Event

import lib.UpdateThread as ut

from lib.FilterManager import FilterManager
from lib.ItemHelper import *
from lib.NotifyThread import NotifyThread
from lib.StateManager import StateManager
from lib.Utility import config, AppException, getJsonFromURL, tmsg


# API URLS
NINJA_API = "http://api.poe.ninja/api/Data/GetStats"
POE_API = "http://api.pathofexile.com/public-stash-tabs?id={}"
# STASH https://www.pathofexile.com/character-window/get-stash-items?league=Legacy&tabs=1&tabIndex=1&accountName=##

ERROR_FNAME = "log\\error.log"
ERROR_JSON_FNAME = "log\\error.json"
ALERT_FNAME = "res\\alert.wav"


class LogLevel(IntEnum):
    Undefined = 0
    Error = 1
    Info = 2
    Debug = 3


class MsgType(IntEnum):
    Control = 0
    Text = 1
    TextError = 2


class ControlMsg(IntEnum):
    Stopped = 0
    UpdateID = 1


class StashScanner:

    def __init__(self, queue):
        self.msg_queue = queue
        self.notifier = NotifyThread()
        self.log_level = LogLevel.Error
        self.stopped = Event()

    def set_log_level(self, log_level):
        self.log_level = log_level

    def send_tmsg(self, msg, log_level=0, msg_type=MsgType.Text):
        self.send_msg(msg, log_level, msg_type, True)

    def send_msg(self, msg, log_level=0, msg_type=MsgType.Text, timed=False):
            if self.log_level >= log_level:
                if timed:
                    msg = tmsg(msg)
                self.msg_queue.put((msg, msg_type))

    def handleResult(self, item, stash, fltr):
        whisperMsg = get_whisper_msg(item, stash)
        price = get_item_price_raw(item, stash)
        if price is None:
            price = ""

        size = get_item_stacksize(item)
        size_str = "" if size == 1 else size

        msg = "{} {}\n{}".format(size_str, get_item_name(item), price).strip()
        self.notifier.send((fltr.getDisplayTitle(), msg, whisperMsg))
        winsound.PlaySound(ALERT_FNAME, winsound.SND_ASYNC | winsound.SND_FILENAME)

        self.send_tmsg(get_item_info(item, stash))
        self.send_msg(whisperMsg)

    def stop(self):
        self.stopped.set()

    def start(self):

        try:
            self.scan()
        except AppException as e:
            self.send_msg(e, LogLevel.Error, MsgType.TextError)
        except Exception as e:
            self.send_msg("Unexpected error occurred: {}".format(e), LogLevel.Error, MsgType.TextError)
            logerror(traceback.format_exc())

        self.notifier.close()
        self.send_msg("Scanning stopped")
        self.send_msg((ControlMsg.Stopped,), msg_type=MsgType.Control)

    def scan(self):
        self.send_msg("Scan initializing..")
        os.makedirs('tmp', exist_ok=True)

        try:
            cm.load()
            self.send_msg("Currency rates loaded successfully.")
        except AppException as e:
            self.send_msg(e, LogLevel.Error, MsgType.TextError)

        try:
            cm.update()
            self.send_msg("Currency rates updated successfully.")
        except AppException as e:
            if cm.initialized:  # only print if load was successful to avoid spam
                self.send_msg(e, LogLevel.Error, MsgType.TextError)

        if not cm.initialized:
            raise AppException("Failed to load currency information.")

        fm = FilterManager()

        filterFallback = False

        try:
            self.send_msg("Generating filters from API..")
            fm.fetchFromAPI()
        except AppException as e:
            filterFallback = True
            self.send_msg(e, LogLevel.Error, MsgType.TextError)

        if filterFallback:
            try:
                self.send_msg("Loading generated filters from a local copy..")
                fm.loadAutoFilters()
            except AppException as e:
                self.send_msg(e, LogLevel.Error, MsgType.TextError)

        self.send_msg("Loading user filters..")
        fm.loadUserFilters()

        self.send_msg("Compiling filters..")
        fm.compileFilters()

        filters = fm.getActiveFilters()

        if not len(filters):
            raise AppException("No active filters loaded")

        self.send_msg("{} filters were loaded. {} filters are active."
                      .format(len(fm.getFilters()), len(filters)))

        for fltr in filters:
            self.send_msg(fltr)

        # INITIAL CHANGE ID
        lastId = ""
        stateMgr = StateManager()

        if stateMgr.getChangeId() == "" or str(config.scan_mode).lower() == "latest":
            self.send_msg("Fetching latest id from API..")
            data = getJsonFromURL(NINJA_API, max_attempts=3)
            if data is None:
                raise AppException("Error retrieving latest id from API, bad response")

            if "nextChangeId" not in data:
                raise AppException("Error retrieving id from API, missing nextChangeId key")

            stateMgr.saveState(data["nextChangeId"])

        stashUrl = POE_API.format(stateMgr.getChangeId())

        updater = ut.UpdateThread(self.stopped, fm, 5*60, self)
        updater.start()
        self.notifier.start()

        c = pycurl.Curl()
        ahead = False
        data = ""
        sleep_time = 0
        num_cores = cpu_count()

        self.send_msg("Scanning started")
        while not self.stopped.wait(sleep_time):
            try:
                #self.send_tmsg("Requesting change id: {}".format(stateMgr.getChangeId()), LogLevel.Info)
                self.send_msg((ControlMsg.UpdateID, stateMgr.getChangeId()), msg_type=MsgType.Control)
                data_count = (0, 0, 0)

                last_req = time.time()
                data = getJsonFromURL(stashUrl, handle=c, max_attempts=1)
                dl_time = time.time() - last_req
                if data is None:
                    self.send_tmsg("Bad response while retrieving data from URL: {}".format(stashUrl), LogLevel.Error, MsgType.TextError)
                    sleep_time = 2
                    continue

                if "error" in data:
                    self.send_tmsg("JSON error response: {}".format(data["error"]))
                    # c.close()
                    c = pycurl.Curl()
                    sleep_time = 10
                    continue

                # Process if its the first time we're in this id
                curId = stateMgr.getChangeId()

                last_parse = time.time()
                #with fm.filters_lock:
                filters = fm.getActiveFilters()

                if lastId != curId:
                    data_count = parse_stashes_parallel(data, filters, stateMgr, self.handleResult, num_cores)
                else:
                    parse_next_id(data, stateMgr)

                    if not ahead:
                        self.send_msg("Reached the end of the river..")
                        ahead = True

                lastId = curId
                stashUrl = POE_API.format(stateMgr.getChangeId())

                parse_time = time.time() - last_parse

                delta = time.time() - last_req
                sleep_time = max(float(config.request_delay) - delta, 0)
                self.send_msg("Iteration time: {:.4f}s, DL: {:.3f}s, Parse: {:.3f}s, Sleeping: {:.3f}s, "
                              "Tabs: {}, League tabs: {}, Items: {}"
                              .format(delta, dl_time, parse_time, sleep_time, *data_count), LogLevel.Debug)

            except pycurl.error as e:
                errno, msg = e.args
                logMsg = tmsg("ERROR {}: {}".format(errno, msg))
                self.send_msg(logMsg, LogLevel.Error, MsgType.TextError)
                logerror(logMsg)

                c.close()
                c = pycurl.Curl()
                sleep_time = 5
                continue
            except Exception as e:
                self.send_msg("Unexpected error occurred: {}".format(e), LogLevel.Error, MsgType.TextError)
                logerror(traceback.format_exc())

                with open(ERROR_JSON_FNAME, "w") as f:
                    json.dump(data, f, indent=4, separators=(',', ': '))

                c.close()
                c = pycurl.Curl()
                sleep_time = 10


def logerror(msg):
    os.makedirs(os.path.dirname(ERROR_FNAME), exist_ok=True)
    with open(ERROR_FNAME, mode="a") as f:
        f.write(msg + '\n')
