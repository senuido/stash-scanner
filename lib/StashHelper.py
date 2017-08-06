import copy
from itertools import chain

from joblib import Parallel, delayed

from lib.CurrencyManager import cm
from lib.ItemHelper import get_price, Item


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


def parse_stashes_parallel(data, filters, league, budget, stateMgr, resultHandler, numCores):
    item_count = 0
    league_stashes = []
    c_budget = cm.compilePrice(budget) if budget else None

    for stash in data["stashes"]:
        if stash["public"] and stash["items"] and stash["items"][0]["league"] == league:
            item_count += len(stash["items"])
            league_stashes.append(stash)

    results = Parallel(n_jobs=numCores)(delayed(parse_stash)(stash, filters, c_budget) for stash in league_stashes)

    for item, stash, fltr in chain.from_iterable(results):
        if stateMgr.addItem(item.id, item.get_price_raw(get_stash_price_raw(stash)), stash["accountName"]):
            resultHandler(copy.deepcopy(item), copy.copy(stash), copy.deepcopy(fltr))

    parse_next_id(data, stateMgr)
    return len(data["stashes"]), len(league_stashes), item_count


def parse_stash(stash, filters, c_budget):

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