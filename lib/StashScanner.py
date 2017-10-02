import itertools
import json
import logging
import os
import pycurl
import time
from contextlib import closing
from datetime import datetime
from multiprocessing.pool import Pool
from queue import Empty, Full
from threading import Event
from urllib.parse import urljoin

import requests

from lib.Downloader import Downloader, get_delta
from lib.UpdateThread import UpdateThread
from lib.CompiledFilter import CompiledFilter
from lib.CurrencyManager import cm
from lib.FilterManager import fm
from lib.ItemHelper import *
from lib.ItemHelper import Item, ItemType, ItemSocket, ItemProperty
from lib.NotifyThread import NotifyThread
from lib.ParserThread import ParserThread
from lib.SearchParams import SearchParams
from lib.StashHelper import parse_next_id, parse_stashes_parallel, get_stash_price_raw
from lib.StateManager import StateManager
from lib.Utility import config, AppException, getJsonFromURL, msgr, logexception, getBytesFromURL, isAbsoluteUrl, \
    dround, getBaseUrl, POE_NINJA_API

# import pstats
# from io import StringIO

# API URLS
NINJA_API = urljoin(POE_NINJA_API, "GetStats")
POE_API = "http://api.pathofexile.com/public-stash-tabs?id={}"
POE_BETA_API = "http://betaapi.pathofexile.com/api/public-stash-tabs?id={}"
# STASH https://www.pathofexile.com/character-window/get-stash-items?league=Legacy&tabs=1&tabIndex=1&accountName=##

JSON_ERROR_FNAME = "log\\error.json"
ITEM_ERROR_FNAME = 'log\\item_error.json'


class StashScanner:
    def __init__(self):
        self.stateMgr = StateManager()

        self.notifier = NotifyThread()
        self.updater = UpdateThread(fm, 10 * 60)
        self.parser = None
        self.downloader = None
        self._stop = Event()

        self.poe_api_url = None
        self.league = None

    def stop(self):
        self._stop.set()

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
            msgr.send_msg(
                "Unexpected error while processing item {}. Item details will not be provided.".format(item.name),
                logging.WARN)
            item_info = None
            logexception()
            with open(ITEM_ERROR_FNAME, mode='w') as f:
                json.dump(item, f, indent=4, separators=(',', ': '))

        msgr.send_msg(whisper_msg, tag=item_info)

    def start(self):
        try:
            self.scan()
        except AppException as e:
            msgr.send_msg(e, logging.ERROR)
        except BaseException as e:
            msgr.send_msg('Unexpected error occurred: {}. Error details logged to file.'.format(e), logging.ERROR)
            logexception()
        finally:
            self.notifier.stop()
            self.updater.stop()

            if self.downloader:
                self.downloader.stop()
            if self.parser:
                self.parser.stop()

            if self.downloader:
                self.downloader.join()

            if self.parser:
                self.parser.join()

            self.stateMgr.close()  # after parser is closed so we don't interfere with pending saves

            if self.updater.is_alive():
                self.updater.join()

            if self.notifier.is_alive():
                self.notifier.join()

            msgr.send_msg("Scanning stopped")
            msgr.send_stopped()

    def scan(self):
        msgr.send_msg("Scan initializing..")
        os.makedirs('tmp', exist_ok=True)
        os.makedirs('log', exist_ok=True)

        is_beta = config.league.lower().startswith('beta ')
        if is_beta:
            self.poe_api_url = POE_BETA_API
            self.league = re.sub('beta ', '', config.league, flags=re.IGNORECASE)
        else:
            self.poe_api_url = POE_API
            self.league = config.league

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

        if fm.needUpdate:
            try:
                msgr.send_msg("Generating filters from API..")
                fm.fetchFromAPI()
            except AppException as e:
                # filterFallback = True
                msgr.send_msg(e, logging.ERROR)

        msgr.send_msg('Compiling filters..', logging.INFO)
        fm.compileFilters(force_validation=True)

        filters = fm.getActiveFilters()

        if not len(filters):
            raise AppException("No filters are active. Stopping..")

        self.stateMgr.loadState()
        if self.stateMgr.getChangeId() == "" or str(config.scan_mode).lower() == "latest":
            msgr.send_msg("Fetching latest id from API..")
            latest_id = self._get_latest_id(is_beta)

            if latest_id:
                if get_delta(self.stateMgr.getChangeId(), latest_id) > 0:
                    self.stateMgr.saveState(latest_id)
                else:
                    msgr.send_msg('Saved ID is more recent, continuing..')
            elif not self._stop.is_set():
                raise AppException("Failed retrieving latest ID from API")

        self.updater.start()
        self.notifier.start()

        get_next = True

        msgr.send_msg("Scanning started")
        msgr.send_update_id(self.stateMgr.getChangeId())
        while not self._stop.is_set():
            if self.downloader is None or not self.downloader.is_alive():
                if self.downloader:
                    msgr.send_msg("Download thread ended abruptly. Restarting it..", logging.WARN)
                self.downloader = Downloader(self.stateMgr.getChangeId(), conns=config.max_conns)
                self.downloader.start()

            if self.parser is None or not self.parser.is_alive() and not self.parser.signal_stop:
                if self.parser:
                    msgr.send_msg("Parser thread ended abruptly. Restarting it..", logging.WARN)
                if config.num_workers > 0:
                    workers = config.num_workers
                else:
                    workers = max((os.cpu_count() or 1) - 1, 1)

                self.parser = ParserThread(workers, self.league, self.stateMgr, self.handleResult)
                self.parser.start()

            try:
                if get_next:
                    req_id, resp = self.downloader.get(timeout=0.5)
                    get_next = False

                self.parser.put(req_id, resp, timeout=0.5)
                get_next = True
            except Full:
                msgr.send_msg("Parser queue is full.. waiting for parser..", logging.WARN)
            except Empty:
                continue

    def _get_latest_id(self, is_beta):
        latest_id = None
        failed_attempts = 0
        sleep_time = 0

        if is_beta:
            ninja_api_nextid_field = 'next_beta_change_id'
        else:
            ninja_api_nextid_field = 'next_change_id'

        while not self._stop.wait(sleep_time) and not latest_id:
            try:
                data = getJsonFromURL(NINJA_API)
                if data is None:
                    msgr.send_msg("Error retrieving latest id from API, bad response", logging.WARN)
                elif ninja_api_nextid_field not in data:
                    raise AppException(
                        "Error retrieving latest id from API, missing {} key".format(ninja_api_nextid_field))
                else:
                    latest_id = data[ninja_api_nextid_field]
                    break
            except pycurl.error as e:
                errno, msg = e.args
                msgr.send_tmsg("Connection error {}: {}".format(errno, msg), logging.WARN)
            finally:
                failed_attempts += 1
                sleep_time = min(2 ** failed_attempts, 30)

        return latest_id

    def getStatistics(self):
        dler = self.downloader
        parser = self.parser

        stats = {}

        if dler:
            stats.update(dler.get_stats())
        if parser:
            stats.update(parser.get_stats())

        return stats

    # def _get_next_id(self, request_id, timeout=5):
    #     try:
    #         with closing(requests.get(self.poe_api_url.format(request_id), stream=True, timeout=timeout)) as r:
    #             # r.raw.decode_content = True
    #
    #             for chunk in r.iter_content(chunk_size=1024):
    #                 if chunk:  # filter out keep-alive new chunks
    #                     next_id = self._peek_id(chunk)
    #                     return next_id
    #     except requests.exceptions.Timeout as e:
    #         msgr.send_msg('Climb timeout: {}'.format(e), logging.DEBUG)
    #     except requests.RequestException as e:
    #         msgr.send_msg('Climb request failed. {}'.format(e), logging.DEBUG)
    #
    # def _peek_id(self, data):
    #     m = re.search(b'"next_change_id":\s*"([0-9\-]+)"', data)
    #     if m:
    #         return m.group(1).decode()
    #     return None

    @staticmethod
    def clearLeagueData():
        fm.clearCache()
        cm.clearCache()
        StateManager.clearCache()


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

        self.tier = item.tier
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

        self.max_sockets = item.get_max_sockets()
        self.type_max_sockets = item.get_type_max_sockets()
        self.sockets = [ItemSocket(socket) for socket in item.sockets]
        self.links_string = item.get_item_links_string()
        self.requirements = [ItemProperty(prop) for prop in item.requirements]
        self.properties = [ItemProperty(prop) for prop in itertools.chain(item.properties, item.additional_properties)]
        self.raw_price = item.get_price_raw(get_stash_price_raw(stash))
        self.price_display = item.get_item_price_display()
        self.whisper_msg = item.get_whisper_msg(stash)

        self.filter_params = SearchParams.genFilterSearch(item, cf).convert()
        self.item_params = SearchParams.genItemSearch(item, cf).convert()

        self.x = item.x
        self.y = item.y
        self.w = item.w
        self.h = item.h

        self.icon = item.icon
        if not isAbsoluteUrl(self.icon):
            self.icon = urljoin(baseUrl, self.icon)

        self.filter_name = cf.getDisplayTitle()
        self.filter_totals = cf.getDisplayTotals(item)

        try:
            val = fm.compiled_item_prices[cf.fltr.id]
            self.profit = val - item.c_price if item.c_price is not None else None
            self.item_value = dround(val, 1), cm.toFull('chaos')
        except KeyError:
            self.item_value = None
            self.profit = None