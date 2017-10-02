import threading
import queue
from tkinter import Tk, Toplevel, messagebox
from tkinter.constants import *
from tkinter.simpledialog import Dialog
from tkinter.ttk import Progressbar, Label, Frame, Button, Style

import time


_MSG_UPDATE = 0
_MSG_CLOSE = 1
_MSG_NOTIFY = 2

class LoadingScreen(Toplevel):
    def __init__(self, master, determinate=True, *args, **kwargs):
        self._queue = queue.Queue()

        super().__init__(master, *args, **kwargs)
        self.withdraw()
        # if master.winfo_viewable():
        #     self.transient(master)
        # style = Style()
        # style.configure('LoadingScreen.TFrame', padding=0, bg='black')

        self.determinate = determinate
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
        pb_mode = 'determinate' if self.determinate else 'indeterminate'
        self.pb_progress = Progressbar(self.frm, mode=pb_mode)
        self.pb_progress.grid(row=1, column=0, sticky='ew')

        self.update_idletasks()
        self.wm_overrideredirect(1)
        self.master.bind('<Configure>', self.updatePosition, add='+')
        self.updatePosition()

        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.focus_set()

        if not self.determinate:
            # self.pb_progress.config(mode='determinate')
            self.pb_progress.start(10)

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
                    if self.determinate:
                        self.pb_progress.config(value=progress)
                elif type == _MSG_CLOSE:
                    self.destroy()
                elif type == _MSG_NOTIFY:
                    title, message = args
                    messagebox.showwarning(title, message, parent=self)

        except queue.Empty:
            pass

        self.after(100, self.processMessages)

    def close(self):
        self._queue.put((_MSG_CLOSE, None))

    def updateStatus(self, text, progress=0):
        self._queue.put((_MSG_UPDATE, (text, progress)))

    def notifyMessage(self, title, message):
        self._queue.put((_MSG_NOTIFY, (title, message)))


if __name__ == '__main__':
    root = Tk()

    frm = Frame(root, relief='sunken')
    frm.grid()

    lbl = Label(frm, text='Main Window')
    lbl.grid()

    pb = Progressbar(frm, mode='indeterminate')
    pb.grid()

    def load_data(event=None):
        ls = LoadingScreen(root, determinate=False)

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