import itertools
import json
import logging
import os
import pycurl
import time
from contextlib import closing
from datetime import datetime
from multiprocessing.pool import Pool
from threading import Event
from urllib.parse import urljoin

import requests

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
    dround, getBaseUrl

# import pstats
# from io import StringIO

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
        self.parser = None
        self._stop = Event()
        # self._stopped = Event()

        self.poe_api_url = None
        self.league = None

    def stop(self):
        self._stop.set()

    # def is_stopped(self):
    #     return self._stopped.is_set()

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
        except Exception as e:
            msgr.send_msg("Fatal unexpected error occurred: {}. Error details logged to file.".format(e), logging.ERROR)
            logexception()
        except BaseException as e:
            msgr.send_msg('Unexpected exception: {}. Error details logged to file.'.format(e), logging.ERROR)
            logexception()
        finally:
            self.stop()
            self.notifier.close()
            self.stateMgr.close()
            if self.parser:
                self.parser.join()
            self.notifier.join()
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

        climb = False
        self.stateMgr.loadState()
        if self.stateMgr.getChangeId() == "" or str(config.scan_mode).lower() == "latest":
            msgr.send_msg("Fetching latest id from API..")
            climb = True # use config val
            latest_id = self._get_latest_id(is_beta)

            if latest_id:
                self.stateMgr.saveState(latest_id)
            else:
                raise AppException("Failed retrieving latest ID from API")

        updater = UpdateThread(self._stop, fm, 10 * 60)
        updater.start()
        self.notifier.start()

        c = pycurl.Curl()
        reached_end = False
        last_reached_end = None
        last_req = 0
        delay_time = 0
        num_cores = os.cpu_count() or 1
        failed_attempts = 0

        self.parser = ParserThread(self._stop, num_cores, self.league, self.stateMgr, self.handleResult)
        self.parser.start()

        def get_sleep_time():
            if failed_attempts:
                sleep_time = max(min(2 ** failed_attempts, 30), config.request_delay - time.time() + last_req)
                msgr.send_msg('Retrying in {} seconds..'.format(sleep_time), logging.DEBUG)
            else:
                sleep_time = delay_time

            return sleep_time

        request_id = self.stateMgr.getChangeId()

        def get_delta(prev_id, curr_id):
            l1 = [int(n) for n in prev_id.split('-')]
            l2 = [int(n) for n in curr_id.split('-')]
            return sum(map(lambda x, y: int(y) - int(x), l1, l2))

        res = []
        climb_deltas = []
        climb_failures = 0
        climb_start = None
        climb_timeout = 200
        b_parser_wait = False
        init_climb = True

        with requests.Session() as s:
            s.headers.update({'Accept-Encoding': 'gzip, deflate'})

            while not self._stop.wait(get_sleep_time()):
                try:
                    msgr.send_update_id(request_id)
                    stashUrl = self.poe_api_url.format(request_id)

                    if climb:
                        if init_climb:
                            msgr.send_msg("Skipping ahead.. please wait..")
                            climb_failures = 0
                            climb_start = time.time()
                            init_climb = False

                        sx = time.time()
                        next_id = self._get_next_id(request_id)
                        get_time = time.time() - sx
                        if next_id is None:
                            climb_failures += 1
                        else:
                            climb_failures = 0
                            id_delta = get_delta(request_id, next_id)

                            res.append(get_time)
                            climb_deltas.append(id_delta)

                            if next_id == request_id:
                                reached_end = True
                                last_reached_end = time.time()
                            else:
                                request_id = next_id

                        measure_len = 10
                        avg_delta = None
                        climb_time = time.time() - climb_start

                        if len(climb_deltas) >= measure_len:
                            avg_delta = sum(climb_deltas) / measure_len

                        if avg_delta and avg_delta < 70:
                            climb = False
                            msgr.send_msg('Climb finished after: {:.3f}s'.format(climb_time))
                        elif climb_time > climb_timeout:
                            climb = False
                            msgr.send_msg('Climb timed out after: {:.3f}s'.format(climb_time), logging.WARN)
                        elif reached_end:
                            climb = False
                            msgr.send_msg('Climb reached end after: {:.3f}s'.format(climb_time))
                        elif climb_failures > 5:
                            climb = False
                            msgr.send_msg('Climb aborted due to failed attempts', logging.WARN)

                        if not climb:
                            msgr.send_msg('Average climb DL: {:.3f}s, Average delta: {}, Reached delta: {}'
                                          .format(sum(res) / len(res), round(sum(climb_deltas) / len(climb_deltas)), round(avg_delta) or 'N/A'), logging.INFO)
                            res = []
                            climb_deltas = []
                            msgr.send_msg("Scanning started")

                        continue

                    if self.parser.queue.qsize() > 5:
                        if not self.parser.is_alive():
                            msgr.send_msg("Parser thread ended abruptly. Restarting it..", logging.WARN)
                            self.parser = ParserThread(self._stop, num_cores, self.league, self.stateMgr, self.handleResult)
                            self.parser.start()
                        if not b_parser_wait:
                            msgr.send_msg("Parser is not keeping up with the request rate. "
                                          "This can put you behind on the data. Waiting for parser..", logging.WARN)
                            b_parser_wait = True
                    else:
                        b_parser_wait = False
                        last_req = time.time()
                        data = getBytesFromURL(stashUrl, handle=c, max_attempts=1)
                        # r = requests.get(stashUrl, timeout=5)
                        # r = s.get(stashUrl, timeout=5)
                        dl_time = time.time() - last_req
                        # data = r.content

                        if data is None:
                            msgr.send_tmsg("Invalid response while retrieving stash data.", logging.ERROR)
                            failed_attempts += 1
                            continue

                        next_id = self._peek_id(data.getbuffer()[:512])
                        # next_id = peek_id(data[:512])
                        if not next_id:
                            msgr.send_tmsg("Full peek", logging.DEBUG)
                            next_id = self._peek_id(data.getvalue())
                            # next_id = peek_id(data)

                        if not next_id:
                            data = json.loads(data.getvalue().decode())
                            if "error" in data:
                                msgr.send_tmsg("Server error response: {}".format(data["error"]), logging.WARN)
                            else:
                                msgr.send_tmsg("ID peek failed and no error response was received.\n{}".format(data.getvalue().decode()), logging.WARN)
                            c.close()
                            c = pycurl.Curl()
                            failed_attempts += 1
                            continue

                        self.parser.put(request_id, data)

                        if request_id == next_id:
                            if not reached_end:
                                msgr.send_msg("Reached the end of the river..", logging.INFO)
                                reached_end = True
                            last_reached_end = datetime.now()

                        request_id = next_id

                        delta = time.time() - last_req
                        delay_time = max(float(config.request_delay) - delta, 0)
                        failed_attempts = 0

                        msgr.send_msg("Iteration time: {:.4f}s, DL: {:.3f}s, Sleeping: {:.3f}s"
                                      .format(delta, dl_time, delay_time), logging.DEBUG)
                except requests.Timeout:
                    pass
                except requests.RequestException as e:
                    print(e)
                except pycurl.error as e:
                    errno, msg = e.args
                    msgr.send_tmsg("Connection error {}: {}".format(errno, msg), logging.WARN)
                    c.close()
                    c = pycurl.Curl()
                    failed_attempts += 1
                    continue

                except Exception as e:
                    msgr.send_msg("Unexpected error occurred: {}. Error details logged to file.".format(e), logging.ERROR)
                    logexception()
                    # with open(JSON_ERROR_FNAME, "w") as f:
                    #     json.dump(data, f, indent=4, separators=(',', ': '))
                    c.close()
                    c = pycurl.Curl()
                    failed_attempts += 1

        # pr.disable()
        # s = StringIO()
        # sortby = 'cumulative'
        # ps = pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby)
        # ps.print_stats()
        # print(s.getvalue())

    def _get_latest_id(self, is_beta):
        latest_id = None
        failed_attempts = 0
        sleep_time = 0

        if is_beta:
            ninja_api_nextid_field = 'nextBetaChangeId'
        else:
            ninja_api_nextid_field = 'nextChangeId'

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

    def _get_next_id(self, request_id, timeout=5):
        try:
            with closing(requests.get(self.poe_api_url.format(request_id), stream=True, timeout=timeout)) as r:
                # r.raw.decode_content = True

                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        next_id = self._peek_id(chunk)
                        return next_id
        except requests.exceptions.Timeout as e:
            msgr.send_msg('Climb timeout: {}'.format(e), logging.DEBUG)
        except requests.RequestException as e:
            msgr.send_msg('Climb request failed. {}'.format(e), logging.DEBUG)

    def _peek_id(self, data):
        m = re.search(b'"next_change_id":\s*"([0-9\-]+)"', data)
        if m:
            return m.group(1).decode()
        return None

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