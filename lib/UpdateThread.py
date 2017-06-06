import weakref
from threading import Thread, Event

import lib.StashScanner
from lib.CurrencyManager import cm
from lib.FilterManager import FilterManager
from lib.Utility import AppException


class UpdateThread(Thread):
    def __init__(self, event, fm, interval, scanner):
        Thread.__init__(self)
        self.stopped = event
        self.fm = fm
        self.interval = interval
        self.scanner = weakref.ref(scanner)

    def run(self):
        while not self.stopped.wait(self.interval):
            scanner = self.scanner()
            compile_filters = False
            try:
                try:
                    cm.update()
                    # self.fm.onCurrencyUpdate()
                    if scanner:
                        scanner.send_msg("Currency rates updated successfully.")
                        compile_filters = True
                except AppException as e:
                    if scanner:
                        scanner.send_msg(e, lib.StashScanner.LogLevel.Error, lib.StashScanner.MsgType.TextError)

                try:
                    self.fm.fetchFromAPI()
                    if scanner:
                        scanner.send_msg("Filters from API updated successfully.")
                    compile_filters = True
                except AppException as e:
                    if scanner:
                        scanner.send_msg(e, lib.StashScanner.LogLevel.Error, lib.StashScanner.MsgType.TextError)

                if compile_filters:
                    self.fm.compileFilters()
            except Exception as e:
                if scanner:
                    scanner.send_msg("Unexpected error while updating: {}".format(e))
            del scanner
