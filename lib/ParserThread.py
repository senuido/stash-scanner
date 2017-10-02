import json
import logging
import os
from collections import deque
from multiprocessing.pool import Pool
from queue import Queue, Empty
from threading import Thread

import time

from lib.CurrencyManager import cm
from lib.FilterManager import fm
from lib.StashHelper import parse_next_id, parse_stashes_parallel
from lib.Utility import msgr, logexception

JSON_ERROR_FNAME = "{}.error.json"
JSON_ERROR_DIR = "log\\"

class ParserThread(Thread):
    def __init__(self, num_workers, league, stateMgr, resultHandler):
        Thread.__init__(self)
        self.queue = Queue(maxsize=25)
        self.num_workers = num_workers
        self.league = league
        self.stateMgr = stateMgr
        self.resultHandler = resultHandler
        self._finished = False
        self.signal_stop = False

        self.parse_times = deque(maxlen=20)
        self.parse_speed = deque(maxlen=20)

    def stop(self):
        self._finished = True
        self.queue.put(None)

    def put(self, request_id, data, timeout=None):
        self.queue.put((request_id, data), timeout=timeout)

    def run(self):
        # pr = cProfile.Profile()
        # pr.enable()

        with Pool(processes=self.num_workers) as pool:

            data = None
            request_id = None

            msgr.send_msg('Parser started..', logging.INFO)
            while not self._finished:
                try:
                    item = self.queue.get()
                    if item is None:
                        break

                    request_id, b = item
                    msgr.send_update_id(request_id)

                    last_parse = time.time()
                    data = json.loads(b.getvalue().decode())

                    # snapshot filters and currency information
                    with cm.compile_lock:
                        filters = fm.getActiveFilters()
                        c_budget = cm.compilePrice(fm.budget) if fm.budget else None
                        ccm = cm.toCCM()

                    if not len(filters):
                        msgr.send_msg("No filters are active. Stopping..")
                        self.signal_stop = True
                        break

                    # pr.enable()
                    tabs, league_tabs, items = parse_stashes_parallel(data, filters, ccm, self.league, c_budget,
                                                            self.stateMgr, self.resultHandler, self.num_workers, pool)

                    # pr.disable()

                    # parse_next_id(data, self.stateMgr)

                    parse_time = time.time() - last_parse
                    speed = items / max(parse_time, 0.001)
                    self.parse_speed.append(speed)
                    self.parse_times.append(parse_time)

                    msgr.send_msg("Parse: {:.3f}s, Tabs: {}, League tabs: {}, Items: {}"
                                  .format(parse_time, tabs, league_tabs, items), logging.DEBUG)
                # except Empty:
                #     pass
                except Exception as e:
                    msgr.send_msg("Unexpected error occurred while parsing: {}. Error details logged to file. ID: {}".format(e, request_id),
                                  logging.ERROR)
                    logexception()
                    if data:
                        fname = os.path.join(JSON_ERROR_DIR, JSON_ERROR_FNAME.format(request_id))
                        with open(fname, "w") as f:
                            json.dump(data, f, indent=4, separators=(',', ': '))

            msgr.send_msg('Parser stopped', logging.INFO)

    def get_stats(self):
        stats = {}

        stats['parse-time'] = sum(self.parse_times) / len(self.parse_times) if len(self.parse_times) else 0
        stats['parse-speed'] = sum(self.parse_speed) / len(self.parse_speed) if len(self.parse_speed) else 0

        return stats