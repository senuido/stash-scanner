import threading
import queue
from tkinter import Tk, Toplevel
from tkinter.constants import *
from tkinter.simpledialog import Dialog
from tkinter.ttk import Progressbar, Label, Frame, Button, Style

import time

_MSG_UPDATE = 0
_MSG_CLOSE = 1

Dialog

class LoadingScreen(Toplevel):
    def __init__(self, master, *args, **kwargs):
        self._queue = queue.Queue()

        super().__init__(master, *args, **kwargs)
        self.withdraw()
        # if master.winfo_viewable():
        #     self.transient(master)
        # style = Style()
        # style.configure('LoadingScreen.TFrame', padding=0, bg='black')

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.frm_border = Frame(self, borderwidth=2, relief=SOLID)
        self.frm_border.columnconfigure(0, weight=1)
        self.frm_border.rowconfigure(0, weight=1)
        self.frm_border.grid(sticky='nsew')

        self.frm = Frame(self.frm_border)
        self.frm.grid(row=0, column=0, padx=20, pady=20, sticky='nsew')
        self.lbl_info = Label(self.frm)
        self.frm.columnconfigure(0, weight=1, minsize=250)

        self.lbl_info.grid(row=0, column=0, sticky='ew')
        self.pb_progress = Progressbar(self.frm, mode='determinate')
        self.pb_progress.grid(row=1, column=0, sticky='ew')

        self.update_idletasks()
        self.wm_overrideredirect(1)
        self.master.bind('<Configure>', self.updatePosition, add='+')
        self.updatePosition()

        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

        self.after(10, self.processMessages)

    def updatePosition(self, event=None):
        if self.winfo_exists():
            self.update_idletasks()
            x = self.master.winfo_rootx() + self.master.winfo_width() / 2 - self.winfo_width() / 2
            y = self.master.winfo_rooty() + self.master.winfo_height() / 2 - self.winfo_height() / 2
            self.geometry('+%d+%d' % (x, y))

    def processMessages(self):
        try:
            while True:
                type, args = self._queue.get_nowait()
                if type == _MSG_UPDATE:
                    text, progress = args
                    self.lbl_info.config(text=text)
                    self.pb_progress.config(value=progress)
                elif type == _MSG_CLOSE:
                    self.destroy()

        except queue.Empty:
            pass

        self.after(100, self.processMessages)

    def close(self):
        self._queue.put((_MSG_CLOSE, None))

    def updateStatus(self, text, progress):
        self._queue.put((_MSG_UPDATE, (text, progress)))

if __name__ == '__main__':
    root = Tk()

    frm = Frame(root, relief='sunken')
    frm.grid()

    lbl = Label(frm, text='Main Window')
    lbl.grid()

    def load_data(event=None):
        ls = LoadingScreen(root)

        def _load():
            ls.updateStatus('Downloading currency information..', 0)
            time.sleep(2)
            ls.updateStatus('Downloading filters information..', 40)
            time.sleep(2)
            ls.updateStatus('Initializing...', 80)
            time.sleep(2)
            ls.updateStatus('Launching', 100)
            time.sleep(1)
            ls.close()

        threading.Thread(target=_load).start()

    btn = Button(frm, text='Load', command=load_data)
    btn.grid()

    # ls = LoadingScreen(root)
    #
    # def _load():
    #     ls.updateStatus('Downloading currency information..', 0)
    #     time.sleep(2)
    #     ls.updateStatus('Downloading filters information..', 40)
    #     time.sleep(2)
    #     ls.updateStatus('Initializing...', 80)
    #     time.sleep(2)
    #     ls.updateStatus('Launching', 100)
    #     time.sleep(1)
    #     ls.close()
    #
    # threading.Thread(target=_load).start()
    # root.wait_window()

    root.mainloop()