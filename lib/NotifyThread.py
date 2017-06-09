import threading
import time
from queue import Queue

import gntp.notifier
import pyperclip

from lib.Utility import config

_APP_NAME = "Stash Scanner"

class NotifyThread(threading.Thread):
    def __init__(self,):
        threading.Thread.__init__(self)
        self.ntfy_queue = Queue()
        self._running = True
        self.daemon = True
        self.growl = gntp.notifier.GrowlNotifier(
            applicationName=_APP_NAME,
            notifications=["Item Alert"],
            defaultNotifications=["Item Alert"])


    def send(self,item):
        self.ntfy_queue.put(item)

    def close(self):
        self._running = False
        self.ntfy_queue.put(None)
        #self.ntfy_queue.join()

    def run(self):
        self.growl.register()

        while self._running: #
            item = self.ntfy_queue.get()
            if item is None:
                break
            title, msg, whisperMsg = item

            pyperclip.copy(whisperMsg)
            delay = float(config.notification_duration)

            if delay > 0 and self.ntfy_queue.qsize():
                title = "{} ({} more)".format(title, self.ntfy_queue.qsize())

            # gntp.notifier.mini(msg, title=title, applicationName=_APP_NAME)
            self.growl.notify(noteType="Item Alert",
                              title=title,
                              description=msg)

            time.sleep(float(config.notification_duration))
            self.ntfy_queue.task_done()
        self.ntfy_queue.task_done()
