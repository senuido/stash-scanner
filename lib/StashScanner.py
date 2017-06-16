import os
import pycurl
import time
import traceback
import winsound
from enum import IntEnum
from threading import Event

import logging

import lib.UpdateThread as ut
from lib.CurrencyManager import CurrencyInfo
from lib.FilterManager import FilterManager
from lib.ItemHelper import *
from lib.NotifyThread import NotifyThread
from lib.StateManager import StateManager
from lib.Utility import config, AppException, getJsonFromURL, tmsg, MsgType, msgr, logger, logexception

# API URLS
NINJA_API = "http://api.poe.ninja/api/Data/GetStats"
POE_API = "http://api.pathofexile.com/public-stash-tabs?id={}"
# STASH https://www.pathofexile.com/character-window/get-stash-items?league=Legacy&tabs=1&tabIndex=1&accountName=##

ERROR_JSON_FNAME = "log\\error.json"
ALERT_FNAME = "res\\alert.wav"


class StashScanner:

    def __init__(self):
        self.notifier = NotifyThread()
        self.stateMgr = StateManager()
        self._stop = Event()
        # self._stopped = Event()

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

        # msgr.send_tmsg(get_item_info(item, stash))

        try:
            item_info = ItemInfo(item, stash)
        except (KeyError, IndexError) as e:
            msgr.send_msg("Error parsing item info, item details will not be displayed", logging.WARN)
            item_info = None
            logexception()
            with open('log\\item.error', mode='w') as f:
                json.dump(item, f, indent=4, separators=(',', ': '))
            print(json.dumps(item, indent=4, separators=(',', ': ')))
        msgr.send_msg(whisperMsg, tag=item_info)

    def stop(self):
        self._stop.set()

    # def is_stopped(self):
    #     return self._stopped.is_set()

    def start(self):

        try:
            self.scan()
        except AppException as e:
            msgr.send_msg(e, logging.ERROR)
        except Exception as e:
            msgr.send_msg("Fatal unexpected error occurred: {}. Error details logged to file.".format(e), logging.ERROR)
            logexception()

        self.notifier.close()
        self.stateMgr.close()
        msgr.send_msg("Scanning stopped")
        msgr.send_stopped()
        # self._stopped.set()

    def scan(self):
        msgr.send_msg("Scan initializing..")
        os.makedirs('tmp', exist_ok=True)
        os.makedirs('log', exist_ok=True)

        cm.load()
        if cm.initialized:
            msgr.send_msg("Currency information loaded successfully.", logging.INFO)

        try:
            cm.update()
            msgr.send_msg("Currency rates updated successfully.")
        except AppException as e:
            msgr.send_msg(e, logging.ERROR)

        if not cm.initialized:
            raise AppException("Failed to load currency information.")

        fm = FilterManager()

        filterFallback = False

        try:
            msgr.send_msg("Generating filters from API..")
            fm.fetchFromAPI()
        except AppException as e:
            filterFallback = True
            msgr.send_msg(e, logging.ERROR)

        if filterFallback:
            try:
                msgr.send_msg("Loading generated filters from a local copy..", logging.WARN)
                fm.loadAutoFilters()
            except AppException as e:
                msgr.send_msg(e, logging.ERROR)

        msgr.send_msg("Loading user filters..")
        fm.loadUserFilters()

        msgr.send_msg("Compiling filters..")
        fm.compileFilters()

        filters = fm.getActiveFilters()

        if not len(filters):
            raise AppException("No filters are active. Stopping..")

        # msgr.send_msg("{} filters were loaded. {} filters are active."
        #               .format(len(fm.getFilters()), len(filters)))
        #
        # for fltr in filters:
        #     msgr.send_msg(fltr)

        # INITIAL CHANGE ID
        lastId = ""
        self.stateMgr.loadState()

        if self.stateMgr.getChangeId() == "" or str(config.scan_mode).lower() == "latest":
            msgr.send_msg("Fetching latest id from API..")
            data = getJsonFromURL(NINJA_API, max_attempts=3)
            if data is None:
                raise AppException("Error retrieving latest id from API, bad response")

            if "nextChangeId" not in data:
                raise AppException("Error retrieving latest id from API, missing nextChangeId key")

            self.stateMgr.saveState(data["nextChangeId"])

        stashUrl = POE_API.format(self.stateMgr.getChangeId())

        updater = ut.UpdateThread(self._stop, fm, 5 * 60)
        updater.start()
        self.notifier.start()

        c = pycurl.Curl()
        ahead = False
        data = ""
        sleep_time = 0
        num_cores = cpu_count()

        msgr.send_msg("Scanning started")
        while not self._stop.wait(sleep_time):
            try:
                msgr.send_update_id(self.stateMgr.getChangeId())
                data_count = (0, 0, 0)

                last_req = time.time()
                data = getJsonFromURL(stashUrl, handle=c, max_attempts=1)
                dl_time = time.time() - last_req
                if data is None:
                    msgr.send_tmsg("Bad response while retrieving data from URL: {}".format(stashUrl), logging.ERROR)
                    sleep_time = 2
                    continue

                if "error" in data:
                    msgr.send_tmsg("Server error response: {}".format(data["error"]), logging.WARN)
                    # c.close()
                    c = pycurl.Curl()
                    sleep_time = 10
                    continue

                # Process if its the first time we're in this id
                curId = self.stateMgr.getChangeId()

                last_parse = time.time()
                filters = fm.getActiveFilters()

                if lastId != curId:
                    data_count = parse_stashes_parallel(data, filters, self.stateMgr, self.handleResult, num_cores)
                else:
                    parse_next_id(data, self.stateMgr)

                    if not ahead:
                        msgr.send_msg("Reached the end of the river..", logging.INFO)
                        ahead = True

                lastId = curId
                stashUrl = POE_API.format(self.stateMgr.getChangeId())

                parse_time = time.time() - last_parse

                delta = time.time() - last_req
                sleep_time = max(float(config.request_delay) - delta, 0)
                msgr.send_msg("Iteration time: {:.4f}s, DL: {:.3f}s, Parse: {:.3f}s, Sleeping: {:.3f}s, "
                              "Tabs: {}, League tabs: {}, Items: {}"
                              .format(delta, dl_time, parse_time, sleep_time, *data_count), logging.DEBUG)

            except pycurl.error as e:
                errno, msg = e.args
                msgr.send_tmsg("Connection error {}: {}".format(errno, msg), logging.WARN)
                c.close()
                c = pycurl.Curl()
                sleep_time = 5
                continue
            except Exception as e:
                msgr.send_msg("Unexpected error occurred: {}. Error details logged to file.".format(e), logging.ERROR)
                logexception()
                with open(ERROR_JSON_FNAME, "w") as f:
                    json.dump(data, f, indent=4, separators=(',', ': '))

                c.close()
                c = pycurl.Curl()
                sleep_time = 10



