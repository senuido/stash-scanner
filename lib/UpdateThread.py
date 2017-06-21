import logging
from threading import Thread

from lib.CurrencyManager import cm
from lib.Utility import AppException, msgr, logexception


class UpdateThread(Thread):
    def __init__(self, event, fm, interval):
        Thread.__init__(self)
        self.stopped = event
        self.fm = fm
        self.interval = interval

    def run(self):
        while not self.stopped.wait(self.interval):
            currency_updated = False
            filters_updated = False

            try:
                try:
                    cm.update()
                    # msgr.send_msg("Currency rates updated successfully.", logging.INFO)
                    currency_updated = True
                except AppException as e:
                    msgr.send_msg(e, logging.ERROR)

                try:
                    self.fm.fetchFromAPI()
                    # msgr.send_msg("Filters updated successfully.", logging.INFO)
                    filters_updated = True
                except AppException as e:
                    msgr.send_msg(e, logging.ERROR)

                if currency_updated or filters_updated:
                    self.fm.compileFilters()

                if currency_updated and filters_updated:
                    msgr.send_msg("Scheduled update completed successfully.", logging.INFO)
                elif not (currency_updated and filters_updated):
                    msgr.send_msg("Scheduled currency and filters update failed. Retrying in {} seconds.."
                                  .format(self.interval), logging.WARN)
                else:
                    msgr.send_msg("Scheduled update was partially successful.", logging.WARN)
            except Exception as e:
                msgr.send_msg("Unexpected error while updating: {}".format(e), logging.ERROR)
                logexception()
