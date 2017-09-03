import json
import logging
from multiprocessing.pool import Pool
from queue import Queue, Empty
from threading import Thread

import time

from lib.CurrencyManager import cm
from lib.FilterManager import fm
from lib.StashHelper import parse_next_id, parse_stashes_parallel
from lib.Utility import msgr, logexception

JSON_ERROR_FNAME = "log\\error.json"

class ParserThread(Thread):
    def __init__(self, event, num_workers, league, stateMgr, resultHandler):
        Thread.__init__(self)
        self.evt_stop = event
        self.queue = Queue()
        self.num_workers = num_workers
        self.league = league
        self.stateMgr = stateMgr
        self.resultHandler = resultHandler

    def close(self):
        self.evt_stop.set()
        self.queue.put(None)

    def put(self, request_id, data):
        self.queue.put((request_id, data))

    def run(self):
        # pr = cProfile.Profile()
        # pr.enable()

        if self.evt_stop.is_set():
            return

        with Pool(processes=self.num_workers) as pool:

            data = None
            request_id = None

            msgr.send_msg('Parser started..', logging.INFO)
            while not self.evt_stop.is_set():
                try:
                    item = self.queue.get(timeout=0.5)
                    if item is None:
                        break

                    # data_count = (0, 0, 0)
                    request_id, b = item

                    last_parse = time.time()
                    data = json.loads(b.getvalue().decode())
                    # data = json.loads(b.decode())

                    # Process if its the first time we're in this id
                    self.stateMgr.getChangeId()

                    # snapshot filters and currency information
                    with cm.compile_lock:
                        filters = fm.getActiveFilters()
                        c_budget = cm.compilePrice(fm.budget) if fm.budget else None
                        ccm = cm.toCCM()

                    if not len(filters):
                        msgr.send_msg("No filters are active. Stopping..")
                        # self.evt_stop.set()
                        # continue
                        break

                    # pr.enable()
                    data_count = parse_stashes_parallel(data, filters, ccm, self.league, c_budget, self.stateMgr,
                                                        self.resultHandler, self.num_workers, pool)
                    # pr.disable()

                    # parse_next_id(data, self.stateMgr)

                    parse_time = time.time() - last_parse

                    msgr.send_msg("Parse: {:.3f}s, Tabs: {}, League tabs: {}, Items: {}"
                                  .format(parse_time, *data_count), logging.DEBUG)
                except Empty:
                    pass
                except Exception as e:
                    #TODO: tell scanner thread to go back?
                    msgr.send_msg("Unexpected error occurred while parsing: {}. Error details logged to file. ID: {}".format(e, request_id),
                                  logging.ERROR)
                    logexception()
                    if data:
                        with open(JSON_ERROR_FNAME, "w") as f:
                            json.dump(data, f, indent=4, separators=(',', ': '))

            self.evt_stop.set()
            msgr.send_msg('Parser stopped', logging.INFO)