from datetime import datetime

def itemToString(id, item):
    return "{};{};{};{}".format(id, item[0].isoformat(), "" if item[1] is None else item[1], item[2])

def getDateTimeFromString(datestr):
    return datetime.strptime(datestr, '%Y-%m-%dT%H:%M:%S.%f')

class StateManager:
    STATE_ID_FNAME = "cfg\\stateid.dat"
    STATE_FNAME = "cfg\\state.dat"

    def __init__(self):
        self.items = {}
        self.delta = {}
        self.changeid = ""
        self.fState = None
        self.fStateId = None

        self.loadState()

    def addItem(self, id, price, acc):
        b_update = False
        if id not in self.items:
            b_update = True
        else:
            timestamp, curprice, curacc = self.items[id]
            b_update = curprice != price or curacc != acc

        if b_update:
            self.items[id] = (datetime.utcnow(), price, acc)
            self.delta[id] = self.items[id]

        return b_update

    def __saveStateDelta(self):
        if self.fState is None or self.fState.closed:
            self.fState = open(StateManager.STATE_FNAME, mode="a+", encoding="utf-8", errors="replace")
        else:
            self.fState.seek(0, 2)

        for id in self.delta:
            self.fState.write(itemToString(id, self.delta[id]) + "\n")

        self.delta.clear()

    def saveStateItems(self):
        if self.fState is not None:
            self.fState.close()

        self.fState = open(StateManager.STATE_FNAME, mode="w", encoding="utf-8", errors="replace")

        for id in self.items:
            self.fState.write(itemToString(id, self.items[id]) + "\n")

    def saveState(self, id):
        if self.fStateId is None or self.fStateId.closed:
            self.fStateId = open(StateManager.STATE_ID_FNAME, "w")
        else:
            self.fStateId.seek(0)

        self.__saveStateDelta()
        self.fStateId.write(id)
        self.changeid = id

    def __loadStateItems(self):
        try:
            if self.fState is None or self.fState.closed:
                self.fState = open(StateManager.STATE_FNAME, encoding="utf-8", errors="replace")

            line = self.fState.readline()
            while line:
                fields = line.strip('\n').split(sep=";")
                self.items[fields[0]] = [getDateTimeFromString(fields[1]),
                                         None if fields[2] == "" else fields[2],
                                         fields[3]]
                line = self.fState.readline()
        except FileNotFoundError:
            pass

        # This will remove unnecessary entries
        self.saveStateItems()

    def loadState(self):
        try:
            # if self.fStateId is None or self.fStateId.closed:
            #     self.fStateId = open(StateManager.STATE_ID_FNAME, "w+")
            # else:
            #     self.fStateId.seek(0)

            with open(StateManager.STATE_ID_FNAME, "r") as f:
                self.changeid = f.readline().strip('\n')

        except FileNotFoundError:
            self.changeid = ""
        #else:
        self.__loadStateItems()

    # if datetime.now() - self.lastClear > timedelta(minutes=60):
    #     self.clearold()

    # def clearold(self):
    #     currtime = datetime.now()
    #     maxtime = timedelta(minutes=60)
    #
    #     for item in dict(self.items):
    #         if currtime - self.items[item][0] > maxtime:
    #             del self.items[item]
    #
    #     self.lastClear = currtime

    def getChangeId(self):
        return self.changeid
