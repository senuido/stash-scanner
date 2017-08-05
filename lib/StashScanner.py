import json
import logging
import os
import pycurl
import time
from datetime import datetime
from threading import Event

import lib.UpdateThread as ut
from lib.CompiledFilter import CompiledFilter
from lib.FilterManager import FilterManager, fm
from lib.ItemHelper import *
from lib.NotifyThread import NotifyThread
from lib.StateManager import StateManager
from lib.Utility import config, AppException, getJsonFromURL, msgr, logexception, getBaseUrl

# API URLS
NINJA_API = "http://api.poe.ninja/api/Data/GetStats"
POE_API = "http://api.pathofexile.com/public-stash-tabs?id={}"
POE_BETA_API = "http://betaapi.pathofexile.com/api/public-stash-tabs?id={}"
# STASH https://www.pathofexile.com/character-window/get-stash-items?league=Legacy&tabs=1&tabIndex=1&accountName=##

JSON_ERROR_FNAME = "log\\error.json"
ITEM_ERROR_FNAME = 'log\\item_error.json'


class StashScanner:
    def __init__(self):
        self.notifier = NotifyThread()
        self.stateMgr = StateManager()
        self._stop = Event()
        # self._stopped = Event()

        self.poe_api_url = None
        self.league = None

    def handleResult(self, item, stash, fltr):
        whisper_msg = item.get_whisper_msg(stash)

        if config.notify:
            price = item.get_price_raw(get_stash_price_raw(stash)) or ''
            size_str = "" if item.stacksize == 1 else item.stacksize

            msg = "{} {}\n{}".format(size_str, item.name, price).strip()
            self.notifier.send((fltr.getDisplayTitle(), msg, item.get_whisper_msg(stash)))

        try:
            item_info = ItemResult(item, stash, getBaseUrl(self.poe_api_url), fltr)
        except (KeyError, IndexError) as e:
            msgr.send_msg("Unexpected error while processing item {}. Item details will not be provided.".format(item.name), logging.WARN)
            item_info = None
            logexception()
            with open(ITEM_ERROR_FNAME, mode='w') as f:
                json.dump(item, f, indent=4, separators=(',', ': '))

        msgr.send_msg(whisper_msg, tag=item_info)

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

        is_beta = config.league.lower().startswith('beta ')
        if is_beta:
            self.poe_api_url = POE_BETA_API
            self.league = re.sub('beta ', '', config.league, flags=re.IGNORECASE)
            ninja_api_nextid_field = 'nextBetaChangeId'
        else:
            self.poe_api_url = POE_API
            self.league = config.league
            ninja_api_nextid_field = 'nextChangeId'

        # cm.load()
        # if cm.initialized:
        #     msgr.send_msg("Currency information loaded successfully.", logging.INFO)

        # assertions
        if not cm.initialized:
            raise AppException("Currency information must be initialized before starting a scan.")
        if not fm.initialized:
            raise AppException("Filters information must be initialized before starting a scan.")

        if cm.needUpdate:
            try:
                cm.update()
                msgr.send_msg("Currency rates updated successfully.")
            except AppException as e:
                msgr.send_msg(e, logging.ERROR)
                if cm.initialized:
                    msgr.send_msg('Using currency information from a local copy..', logging.WARN)

        # if not cm.initialized:
        #     raise AppException("Failed to load currency information.")

        # filterFallback = False

        if fm.needUpdate:
            try:
                msgr.send_msg("Generating filters from API..")
                fm.fetchFromAPI()
            except AppException as e:
                # filterFallback = True
                msgr.send_msg(e, logging.ERROR)

        # if filterFallback:
        #     try:
        #         msgr.send_msg("Loading generated filters from a local copy..", logging.WARN)
        #         fm.loadAutoFilters()
        #     except AppException as e:
        #         msgr.send_msg(e, logging.ERROR)

        # msgr.send_msg("Loading user filters..")
        # fm.loadUserFilters()
        # msgr.send_msg("Validating filters..")
        # verrors = fm.validateFilters()

        # for e in verrors:
        #     msgr.send_msg(e, logging.ERROR)
        #
        # if verrors:
        #     raise AppException("Error while validating filters. Correct the errorrs using the editor and start again. Stopping..")

        msgr.send_msg('Compiling filters..', logging.INFO)
        fm.compileFilters(force_validation=True)

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

            if ninja_api_nextid_field not in data:
                raise AppException("Error retrieving latest id from API, missing {} key".format(ninja_api_nextid_field))

            self.stateMgr.saveState(data[ninja_api_nextid_field])

        stashUrl = self.poe_api_url.format(self.stateMgr.getChangeId())

        updater = ut.UpdateThread(self._stop, fm, 10 * 60)
        updater.start()
        self.notifier.start()

        c = pycurl.Curl()
        ahead = False
        data = ""
        last_req = 0
        delay_time = 0
        num_cores = os.cpu_count()
        failed_attempts = 0

        def get_sleep_time():
            if failed_attempts:
                sleep_time = max(min(2 ** failed_attempts, 30), config.request_delay - time.time() + last_req)
            else:
                sleep_time = delay_time

            return sleep_time

        msgr.send_msg("Scanning started")
        while not self._stop.wait(get_sleep_time()):
            try:
                msgr.send_update_id(self.stateMgr.getChangeId())
                data_count = (0, 0, 0)

                last_req = time.time()
                data = getJsonFromURL(stashUrl, handle=c, max_attempts=1)
                dl_time = time.time() - last_req

                if data is None:
                    msgr.send_tmsg("Invalid response while retrieving stash data.", logging.ERROR)
                    # sleep_time = 2
                    failed_attempts += 1
                    continue

                if "error" in data:
                    msgr.send_tmsg("Server error response: {}".format(data["error"]), logging.WARN)
                    # c.close()
                    c = pycurl.Curl()
                    # sleep_time = 10
                    failed_attempts += 1
                    continue

                # Process if its the first time we're in this id
                curId = self.stateMgr.getChangeId()

                last_parse = time.time()
                filters = fm.getActiveFilters()

                if not len(filters):
                    msgr.send_msg("No filters are active. Stopping..")
                    # self._stop.set()
                    # continue
                    break

                if lastId != curId:
                    data_count = parse_stashes_parallel(data, filters, self.league, self.stateMgr, self.handleResult, num_cores)
                else:
                    parse_next_id(data, self.stateMgr)

                    if not ahead:
                        msgr.send_msg("Reached the end of the river..", logging.INFO)
                        ahead = True

                lastId = curId
                stashUrl = self.poe_api_url.format(self.stateMgr.getChangeId())

                parse_time = time.time() - last_parse

                delta = time.time() - last_req
                delay_time = max(float(config.request_delay) - delta, 0)
                msgr.send_msg("Iteration time: {:.4f}s, DL: {:.3f}s, Parse: {:.3f}s, Sleeping: {:.3f}s, "
                              "Tabs: {}, League tabs: {}, Items: {}"
                              .format(delta, dl_time, parse_time, delay_time, *data_count), logging.DEBUG)

                failed_attempts = 0

            except pycurl.error as e:
                errno, msg = e.args
                msgr.send_tmsg("Connection error {}: {}".format(errno, msg), logging.WARN)
                c.close()
                c = pycurl.Curl()
                # sleep_time = 5
                failed_attempts += 1
                continue
            except Exception as e:
                msgr.send_msg("Unexpected error occurred: {}. Error details logged to file.".format(e), logging.ERROR)
                logexception()
                with open(JSON_ERROR_FNAME, "w") as f:
                    json.dump(data, f, indent=4, separators=(',', ': '))

                c.close()
                c = pycurl.Curl()
                failed_attempts += 1
                # sleep_time = 10

    @staticmethod
    def clearLeagueData():
        fm.clearCache()
        cm.clearCache()
        StateManager.clearCache()



# used to expose specific item result info to ui
# intentionally throws exceptions so we're forced to update enums when changes are made
class ItemResult:
    def __init__(self, item, stash, baseUrl, cf):
        if not isinstance(item, Item):
            raise TypeError('item is expected to be of type Item')
        if not isinstance(cf, CompiledFilter):
            raise TypeError('cf is expected to be of type CompiledFilter')

        self.date = datetime.now()
        self.id = item.id
        self.ilvl = item.ilvl
        self.price = item.price
        self.name = item.name
        self.type = ItemType(item.type)
        self.identified = item.identified
        self.corrupted = item.corrupted
        self.mirrored = item.mirrored
        self.stacksize = item.stacksize
        self.note = item.note

        self.mods = item.mods
        self.implicit = item.implicit
        self.explicit = item.explicit
        self.craft = item.craft
        self.enchant = item.enchant
        self.utility = item.utility
        self.prophecy = item.prophecy

        self.quality = item.quality
        self.level = item.level
        self.exp = item.exp
        # self.phys = item.phys
        # self.elem = item.elem
        self.aps = item.aps
        self.dps = item.dps
        self.pdps = item.pdps
        self.edps = item.edps

        self.armour = item.armour
        self.evasion = item.evasion
        self.es = item.es
        self.block = item.block
        self.crit = item.crit

        self.sockets = [ItemSocket(socket) for socket in item.sockets]
        self.links_string = item.get_item_links_string()
        self.requirements = [ItemProperty(prop) for prop in item.requirements]
        self.properties = [ItemProperty(prop) for prop in itertools.chain(item.properties, item.additional_properties)]
        self.raw_price = item.get_price_raw(get_stash_price_raw(stash))
        self.price_display = item.get_item_price_display()
        self.whisper_msg = item.get_whisper_msg(stash)

        self.x = item.x
        self.y = item.y
        self.w = item.w
        self.h = item.h

        self.icon = item.icon
        if not isAbsoluteUrl(self.icon):
            self.icon = urljoin(baseUrl, self.icon)

        self.filter_name = cf.getDisplayTitle()
        self.filter_totals = cf.getDisplayTotals(item)