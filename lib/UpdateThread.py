from threading import Thread, Event

import logging

from lib.CurrencyManager import cm
from lib.FilterManager import FilterManager
from lib.Utility import AppException, msgr, logexception


class UpdateThread(Thread):
    def __init__(self, event, fm, interval):
        Thread.__init__(self)
        self.stopped = event
        self.fm = fm
        self.interval = interval

    def run(self):
        while not self.stopped.wait(self.interval):
            compile_filters = False
            try:
                try:
                    cm.update()
                    # msgr.send_msg("Currency rates updated successfully.", logging.INFO)
                    compile_filters = True
                except AppException as e:
                    msgr.send_msg(e, logging.ERROR)

                try:
                    self.fm.fetchFromAPI()
                    # msgr.send_msg("Filters updated successfully.", logging.INFO)
                    compile_filters = True
                except AppException as e:
                    msgr.send_msg(e, logging.ERROR)

                if compile_filters:
                    self.fm.compileFilters()
                    msgr.send_msg("Scheduled update completed successfully.", logging.INFO)
                else:
                    msgr.send_msg("Scheduled currency and filters update failed. Retrying in {} seconds.."
                                  .format(self.interval), logging.WARN)
            except Exception as e:
                msgr.send_msg("Unexpected error while updating: {}".format(e), logging.ERROR)
                logexception()
