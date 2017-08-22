import copy
from itertools import chain

from lib.CurrencyManager import cm
from lib.ItemHelper import get_price, Item
from lib.Utility import round_up
import multiprocessing

import os
import sys

try:
    # Python 3.4+
    if sys.platform.startswith('win'):
        import multiprocessing.popen_spawn_win32 as forking
    else:
        import multiprocessing.popen_fork as forking
except ImportError:
    import multiprocessing.forking as forking

if sys.platform.startswith('win'):
    # First define a modified version of Popen.
    class _Popen(forking.Popen):
        def __init__(self, *args, **kw):
            if hasattr(sys, 'frozen'):
                # We have to set original _MEIPASS2 value from sys._MEIPASS
                # to get --onefile mode working.
                os.putenv('_MEIPASS2', sys._MEIPASS)
            try:
                super(_Popen, self).__init__(*args, **kw)
            finally:
                if hasattr(sys, 'frozen'):
                    # On some platforms (e.g. AIX) 'os.unsetenv()' is not
                    # available. In those cases we cannot delete the variable
                    # but only set it to the empty string. The bootloader
                    # can handle this case.
                    if hasattr(os, 'unsetenv'):
                        os.unsetenv('_MEIPASS2')
                    else:
                        os.putenv('_MEIPASS2', '')

    # Second override 'Popen' class with our modified version.
    forking.Popen = _Popen


class StashTab:
    def __init__(self, stash):
        self.name = stash['stash']
        self.items = stash['items']
        self.public = stash['public']
        self.account_name = stash['accountName']
        self.last_char_name = stash['lastCharacterName']
        self.league = self.items[0]['league'] if self.items else None

        self.price = get_price(self.name)

    def get_stash_price_raw(self):
        if self.price is not None:
            return self.name
        return None


def get_stash_price(stash):
    return get_price(stash['stash'])


def get_stash_price_raw(stash):
    if get_stash_price(stash):
        return stash['stash']
    return None


def parse_next_id(data, stateMgr):
    stateMgr.saveState(data["next_change_id"])


def parse_stashes_parallel(data, filters, ccm, league, c_budget, stateMgr, resultHandler, numCores, pool):
    item_count = 0
    league_stashes = []
    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
            item_count += len(stash["items"])
            league_stashes.append(stash)

    # results = Parallel(n_jobs=numCores, verbose=10)(delayed(parse_stash)(stash, filters, c_budget) for stash in league_stashes)
    # results = pool(delayed(parse_stash)(stash, filters, c_budget) for stash in league_stashes)
    # pool = None
    # if pool:
    #TODO: send multiple stashes to reduce overhead
    results = pool.starmap(parse_stash, ((stash, filters, c_budget, ccm) for stash in league_stashes), round_up(len(league_stashes)/numCores))
    # else:
    #     results = (parse_stash(stash, filters, c_budget) for stash in league_stashes)

    for item, stash, fltr in chain.from_iterable(results):
        if stateMgr.addItem(item.id, item.get_price_raw(get_stash_price_raw(stash)), stash["accountName"]):
            resultHandler(copy.deepcopy(item), copy.copy(stash), copy.deepcopy(fltr))

    parse_next_id(data, stateMgr)
    return len(data["stashes"]), len(league_stashes), item_count


def parse_stash(stash, filters, c_budget, ccm):
    cm.fromCCM(ccm)

    results = []
    stash_price = get_stash_price(stash)
    for item in stash["items"]:
        curItem = Item(item, stash_price)

        if within_budget(curItem, c_budget):
            for fltr in filters:
                if fltr.checkItem(curItem):
                    results.append((curItem, stash, fltr))
                    break

    return results


def within_budget(item, c_budget):
    return not (item.c_price is not None and c_budget is not None and item.c_price > c_budget)

# def parse_stashes(data, filters, league, stateMgr, resultHandler):
#     league_tabs = 0
#     item_count = 0
#
#     for stash in data["stashes"]:
#         if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
#             league_tabs += 1
#             item_count += len(stash["items"])
#             for item in stash["items"]:
#                 curItem = Item(item, stash)
#                 for fltr in filters:
#                     if fltr.checkItem(curItem):
#                         if stateMgr.addItem(curItem.id, get_item_price_raw(item, stash), stash["accountName"]):
#                             resultHandler(curItem, stash, fltr)
#                         break
#
#     parse_next_id(data, stateMgr)
#     return len(data["stashes"]), league_tabs, item_count

if __name__ == '__main__':
    multiprocessing.freeze_support()