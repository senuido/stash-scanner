import functools
import json
import pycurl
import re
import traceback
from collections import deque
from io import BytesIO
from queue import Queue, Empty, Full
from threading import Thread, Lock, Event

import time

import logging

from lib.Utility import msgr, logexception, config

TIMEOUT = 30
CONNECT_TIMEOUT = 5
# REQ_DELAY = 0.7
SUFFICIENT_DELTA = 100
URL = "http://api.pathofexile.com/public-stash-tabs?id={}"
RES_QUEUE_MAXSIZE = 50
# START_ID = '65986412-69582870-65115932-75710468-70380757'
# START_ID = '94987699-99693565-93693051-108145998-100918828'
START_ID = '95172882-99885924-93870471-108349815-101111064'

def info(c):
    "Return a dictionary with all info on the last response."
    m = {}
    m['effective-url'] = c.getinfo(pycurl.EFFECTIVE_URL)
    m['http-code'] = c.getinfo(pycurl.HTTP_CODE)
    m['total-time'] = c.getinfo(pycurl.TOTAL_TIME)
    m['namelookup-time'] = c.getinfo(pycurl.NAMELOOKUP_TIME)
    m['connect-time'] = c.getinfo(pycurl.CONNECT_TIME)
    m['pretransfer-time'] = c.getinfo(pycurl.PRETRANSFER_TIME)
    m['redirect-time'] = c.getinfo(pycurl.REDIRECT_TIME)
    m['redirect-count'] = c.getinfo(pycurl.REDIRECT_COUNT)
    # m['size-upload'] = c.getinfo(pycurl.SIZE_UPLOAD)
    m['size-download'] = c.getinfo(pycurl.SIZE_DOWNLOAD)
    # m['speed-upload'] = c.getinfo(pycurl.SPEED_UPLOAD)
    m['header-size'] = c.getinfo(pycurl.HEADER_SIZE)
    m['request-size'] = c.getinfo(pycurl.REQUEST_SIZE)
    m['content-length-download'] = c.getinfo(pycurl.CONTENT_LENGTH_DOWNLOAD)
    m['content-length-upload'] = c.getinfo(pycurl.CONTENT_LENGTH_UPLOAD)
    m['content-type'] = c.getinfo(pycurl.CONTENT_TYPE)
    m['response-code'] = c.getinfo(pycurl.RESPONSE_CODE)
    m['speed-download'] = c.getinfo(pycurl.SPEED_DOWNLOAD)
    # m['ssl-verifyresult'] = c.getinfo(pycurl.SSL_VERIFYRESULT)
    m['filetime'] = c.getinfo(pycurl.INFO_FILETIME)
    m['starttransfer-time'] = c.getinfo(pycurl.STARTTRANSFER_TIME)
    m['redirect-time'] = c.getinfo(pycurl.REDIRECT_TIME)
    m['redirect-count'] = c.getinfo(pycurl.REDIRECT_COUNT)
    m['http-connectcode'] = c.getinfo(pycurl.HTTP_CONNECTCODE)
    # m['httpauth-avail'] = c.getinfo(pycurl.HTTPAUTH_AVAIL)
    # m['proxyauth-avail'] = c.getinfo(pycurl.PROXYAUTH_AVAIL)
    # m['os-errno'] = c.getinfo(pycurl.OS_ERRNO)
    m['num-connects'] = c.getinfo(pycurl.NUM_CONNECTS)
    # m['ssl-engines'] = c.getinfo(pycurl.SSL_ENGINES)
    # m['cookielist'] = c.getinfo(pycurl.INFO_COOKIELIST)
    # m['lastsocket'] = c.getinfo(pycurl.LASTSOCKET)
    # m['ftp-entry-path'] = c.getinfo(pycurl.FTP_ENTRY_PATH)
    return m


def get_delta(prev_id, curr_id):
    l1 = [int(n) for n in prev_id.split('-')]
    l2 = [int(n) for n in curr_id.split('-')]
    return sum(map(lambda x, y: int(y) - int(x), l1, l2))

class Request:
    def __init__(self, req_id, skip_data=False):
        self.req_id = req_id
        self.buffer = BytesIO()
        self.submitted_next = None
        self.added_time = None
        self.submit_time = None
        self.start_time = None
        self.peek_time = None

        self.finished = False
        self.skip_data = skip_data

    def reset(self):
        self.buffer = BytesIO()

    def write(self, dl, data):
        self.buffer.write(data)
        if not self.submitted_next and len(self.buffer.getbuffer()) > 512:
            next_id = self._peek_id(self.buffer.getbuffer()[:512])
            if next_id:
                dl.add_request(next_id)
                self.submitted_next = next_id
                self.peek_time = time.time() - self.start_time

                if self.skip_data:
                    self.finished = True
                    return -1
            # else:
            #     msgr.send_msg("Peek failed, contents: ".format(self.buffer.getvalue().decode()), logging.WARN)

    def _peek_id(self, data):
        m = re.search(b'"next_change_id":\s*"([0-9\-]+)"', data)
        if m:
            return m.group(1).decode()
        return None

    def peek_id(self):
        return self._peek_id(self.buffer.getvalue())

class Downloader(Thread):
    def __init__(self, start_id, conns=2, skip_timeout=120):
        Thread.__init__(self)
        self.m = pycurl.CurlMulti()

        self.handles = [self._create_handle() for i in range(conns)]
        self.free_handles = list(self.handles)
        self.last_request = None

        self.skip_ahead = False
        self.skip_timeout = skip_timeout
        self.dl_deltas = deque(maxlen=10)

        self.req_time = deque(maxlen=20)
        self.queue_time = deque(maxlen=20)
        self.peek_time = deque(maxlen=20)
        self.req_delay_time = deque(maxlen=20)

        self.stat_thread = Thread(target=self.calc_stat)
        self.dps = deque(maxlen=60)
        self.delta_lock = Lock()
        self.delta_count = 0

        # queue for requests so we can ensure a delay between each request
        # use a list instead of an actual queue to be able to choose min ID
        self.req_queue = []
        self.req_queue_lock = Lock()

        # requests by order
        self.requests = []
        self.requests_lock = Lock()

        self.res_queue = Queue(maxsize=RES_QUEUE_MAXSIZE)
        self.evt_stop = Event()

        self.add_request(start_id)

    def calc_stat(self):
        while not self.evt_stop.wait(1):
            if not self.is_alive():
                break

            with self.delta_lock:
                self.dps.append(self.delta_count)
                self.delta_count = 0

    def _create_handle(self):
        c = pycurl.Curl()

        # c.setopt(pycurl.VERBOSE, 1)
        c.setopt(pycurl.CONNECTTIMEOUT, CONNECT_TIMEOUT)
        c.setopt(pycurl.TIMEOUT, TIMEOUT)
        c.setopt(pycurl.ENCODING, 'gzip, deflate')

        return c

    def _prepare_handle(self, c, request):
        c.setopt(pycurl.URL, URL.format(request.req_id))
        c.setopt(pycurl.WRITEFUNCTION, functools.partial(request.write, self))
        c.req = request

    def run(self):
        try:
            msgr.send_msg('Downloader started', logging.INFO)
            if self.skip_ahead:
                msgr.send_msg('Skipping ahead.. please wait..')
            # self.skip_ahead = False

            self.stat_thread.start()

            start_time = time.time()

            while not self.evt_stop.is_set():
                while not self.evt_stop.is_set():
                    with self.req_queue_lock:
                        if self.req_queue and self.free_handles and \
                                (not self.last_request or time.time() - self.last_request >= config.request_delay):

                            # get unfinished request with minimal ID
                            # assumes any request in queue was properly registered with add_request first
                            req_sorted = sorted(self.req_queue, key=lambda r: self.requests.index(r))
                            req = req_sorted[0]
                            self.req_queue.remove(req)

                            # req = self.req_queue.pop(0)  # TODO: choose min ID (only needed if we resubmit failed attempts)
                            handle = self.free_handles.pop(0)
                            self._prepare_handle(handle, req)

                            if self.last_request:
                                delta = time.time() - self.last_request
                            else:
                                delta = 0

                            add_delay = time.time() - req.submit_time
                            self.queue_time.append(add_delay)

                            self.m.add_handle(handle)
                            self.last_request = time.time()
                            req.start_time = self.last_request

                            self.req_delay_time.append(delta)

                            # msgr.send_msg('Added: {}, delta: {:.3f}s, add delay: {:.3f}s'.format(req.req_id, delta, add_delay), logging.DEBUG)

                    ret, num_handles = self.m.perform()
                    if ret != pycurl.E_CALL_MULTI_PERFORM: break


                # Check for curl objects which have terminated, and add them to the freelist
                while not self.evt_stop.is_set():
                    num_q, ok_list, err_list = self.m.info_read()
                    for c in ok_list:
                        self.m.remove_handle(c)
                        cinfo = info(c)
                        # print("Success: {} - {}: total: {:.2f}s, speed: {} KB/s, size: {} KB, "
                        #       "start-transfer: {:.2f}s, pre-transfer: {:.2f}s"
                        #       .format(c.req.req_id, c.getinfo(pycurl.HTTP_CODE), cinfo['total-time'],
                        #               round(cinfo['speed-download']/1024), round(cinfo['size-download']/1024),
                        #               cinfo['starttransfer-time'], cinfo['pretransfer-time']))

                        if cinfo['http-code'] == 200:
                            if not c.req.submitted_next:
                                next_id = c.req.peek_id()
                                if next_id:
                                    msgr.send_msg('Full peek was required for ID: {}'.format(c.req.req_id), logging.INFO)
                                    self.add_request(next_id)
                                    c.req.submitted_next = next_id
                                    c.req.peek_time = time.time() - c.req.start_time

                            if c.req.submitted_next:
                                c.req.finished = True
                            else:
                                msgr.send_msg('Request successful for ID {}, but next ID was not found. Redownloading..'
                                              .format(c.req.req_id), logging.INFO)
                        else:
                            try:
                                err_data = json.loads(c.req.buffer.getvalue().decode())['error']
                                msgr.send_msg('Request for ID {} failed. {} - Code: {}, Message: {}'
                                              .format(c.req.req_id, cinfo['http-code'], err_data['code'], err_data['message']), logging.WARN)
                            except Exception:
                                msgr.send_msg('Request for ID {} failed. {} - {}'.format(c.req.req_id, cinfo['http-code'], c.req.buffer.getvalue().decode()), logging.WARN)

                        # if c.req.finished:
                        #     self.free_handles.append(c)
                        # else:
                        #     c.req.reset()
                        #     self.m.add_handle(c)
                        self.free_handles.append(c)

                        if not c.req.finished:
                            c.req.reset()
                            self._submit(c.req)
                        else:
                            self.req_time.append(cinfo['total-time'])
                            self.peek_time.append(c.req.peek_time)


                    for c, errno, errmsg in err_list:
                        self.m.remove_handle(c)

                        # if c.req.finished:  # for skips?
                        #     self.free_handles.append(c)
                        # else:
                        #     c.req.reset()
                        #     self.m.add_handle(c)
                        self.free_handles.append(c)

                        if not c.req.finished:
                            msgr.send_msg("Failed: {} - Code: {}, {}. Redownloading.."
                                          .format(c.req.req_id, errno, errmsg), logging.INFO)
                            c.req.reset()
                            self._submit(c.req)
                        else:
                            cinfo = info(c)
                            self.req_time.append(cinfo['total-time'])
                            self.peek_time.append(c.req.peek_time)

                    if num_q == 0:
                        break

                with self.requests_lock:
                    while self.requests and self.requests[0].finished:
                        req = self.requests.pop(0)

                        delta = get_delta(req.req_id, req.submitted_next)
                        self.dl_deltas.append(delta)
                        with self.delta_lock:
                            self.delta_count += delta

                        if not req.skip_data:
                            try:
                                self.res_queue.put((req.req_id, req.buffer), timeout=1)
                            except Full:
                                msgr.send_msg('Result queue is full.. waiting for consumer to free slots..', logging.WARN)
                                self.res_queue.put((req.req_id, req.buffer))

                if self.skip_ahead:
                    if self.dl_deltas and len(self.dl_deltas) == self.dl_deltas.maxlen:
                        avg_delta = sum(self.dl_deltas) / len(self.dl_deltas)
                        # msgr.send_msg("Delta avg: {}".format(avg_delta), logging.DEBUG)
                        if avg_delta <= SUFFICIENT_DELTA:
                            msgr.send_msg("Sufficient delta reached ({}) after {:.3f} seconds. Data processing started."
                                          .format(avg_delta, time.time() - start_time))
                            self.skip_ahead = False

                    if self.skip_ahead:
                        passed = time.time() - start_time
                        if passed > self.skip_timeout:
                            msgr.send_msg("Skip ahead timed out after {:.3f} seconds. Data processing started."
                                          .format(passed), logging.WARN)
                            self.skip_ahead = False

                self.m.select(1.0)

                if not len(self.requests):
                    # Should never happen, since there is always a next id.
                    # If it does, parent thread will end up restarting this from last saved point
                    msgr.send_msg('No requests left.. stopping..', logging.WARN)
                    self.stop()
        except Exception as e:
            msgr.send_msg("Unexpected error occurred while downloading: {}. Error details logged to file.".format(e),
                          logging.ERROR)
            logexception()
        finally:
            self._close()
            msgr.send_msg('Downloader stopped', logging.INFO)

    def stop(self):
        self.evt_stop.set()

    def _close(self):
        self.m.close()
        for handle in self.handles:
            handle.close()

    def add_request(self, next_id):
        req = Request(next_id, skip_data=self.skip_ahead)

        with self.requests_lock:
            req.add_time = time.time()
            self.requests.append(req)

        self._submit(req)

    def _submit(self, req):
        with self.req_queue_lock:
            req.submit_time = time.time()
            self.req_queue.append(req)

    def get(self, block=True, timeout=None):
        return self.res_queue.get(block, timeout)

    def get_stats(self):
        stats = {}

        stats['last-req'] = self.last_request
        stats['req-time'] = sum(self.req_time) / len(self.req_time) if len(self.req_time) else 0
        stats['peek-time'] = sum(self.peek_time) / len(self.peek_time) if len(self.peek_time) else 0
        stats['id-delta'] = sum(self.dl_deltas) / len(self.dl_deltas) if len(self.dl_deltas) else None
        stats['queue-time'] = sum(self.queue_time) / len(self.queue_time) if len(self.queue_time) else 0
        stats['req-delay-time'] = sum(self.req_delay_time) / len(self.req_delay_time) if len(self.req_delay_time) else 0
        stats['delta-rate'] = sum(self.dps) / len(self.dps) if len(self.dps) else 0

        return stats


if __name__ == '__main__':

    dler = Downloader(START_ID, conns=8)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)
    # dler.add_request(START_ID)

    dler.start()
    # time.sleep(5)
    # dler.add_request(START_ID)

    time.sleep(100)
    dler.stop()
    print('Requests num: {}, finished requests: {}, result: {}'.format(len(dler.requests), len([req for req in dler.requests if req.finished]), dler.res_queue.qsize()))

    print('\n-- Requests --\n')
    for req in dler.requests:
        print('{}: {}'.format(req.req_id, req.finished))

    print('\n-- Results --\n')
    prev_id = None
    try:
        while True:
            req_id, data = dler.res_queue.get_nowait()

            delta = get_delta(prev_id, req_id) if prev_id else 0
            print('{}: {} KB, Delta: {}'.format(req_id, round(len(data.getvalue())/1024), delta))

            prev_id = req_id
    except Empty:
        pass
