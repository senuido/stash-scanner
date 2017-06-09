import queue
from queue import Queue
from threading import Thread
from tkinter import *
from tkinter.ttk import *

import logging

from lib.StashScanner import StashScanner
from lib.Utility import MsgType, msgr


class AppGUI(Tk):

    BG_COLOR = '#37474F'#263238'#'#455A64'
    DEFAULT_COLOR = '#FFFFFF'#'#ECEFF1'
    WARN_COLOR = '#FDD835'
    ERROR_COLOR = 'red'

    def __init__(self):

        super().__init__()

        self.title("Stash Scanner by Senu")
        self.geometry("1024x600")
        self.center()
        self.create_widgets()

        self.msg_level = logging.INFO
        self.lst_msgs.after(100, self.handle_msgs)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.scanner = None
        self.scan_thread = None

        self.start_scan()

    def create_widgets(self):
        self.configure(padx=10, pady=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.upper_frame = Frame(self, relief='groove')
        self.upper_frame.grid(row=0, sticky='nsew', ipadx=5)
        self.upper_frame.columnconfigure(6, weight=1)
        #
        # self.btn_info = Button(self.upper_frame, text="Info", command=self.set_log_info)
        # self.btn_info.grid(row=0, column=0, padx=(5, 0), pady=5, sticky='ns')
        # self.btn_error = Button(self.upper_frame, text="Normal", command=self.set_log_error)
        # self.btn_error.grid(row=0, column=1, pady=5, sticky='ns')
        # self.btn_dbg = Button(self.upper_frame, text="Debug", command=self.set_log_debug)
        # self.btn_dbg.grid(row=0, column=4, pady=5, sticky='ns')

        self.lbl_msglevel = Label(self.upper_frame, text="Message Level:")
        self.lbl_msglevel.grid(row=0, column=0, padx=(5, 0), pady=5, sticky='ns')

        self.cmb_msglevel = Combobox(self.upper_frame, values=['Error', 'Warning', 'Info', 'Debug'],
                                     state='readonly')
        self.cmb_msglevel.bind('<<ComboboxSelected>>', self.set_msglevel)
        self.cmb_msglevel.set('Info')
        self.cmb_msglevel.grid(row=0, column=1, pady=5, padx=(5, 0), sticky='ns')

        self.btn_clear = Button(self.upper_frame, text="Clear", command=self.clear_msgs)
        self.btn_clear.grid(row=0, column=2, pady=5, padx=(5, 0), sticky='ns')

        self.btn_toggle = Button(self.upper_frame, text="Stop", command=self.toggle_scan)
        self.btn_toggle.grid(row=0, column=3, pady=5, padx=(5, 0), sticky='ns')

        self.lbl_id_value = Label(self.upper_frame, text="", foreground="blue")
        self.lbl_id_value.grid(row=0, column=6, padx=(0, 10), sticky='e')

        self.frame = Frame(self, relief='sunken')
        self.frame.grid(row=1, column=0, sticky='nsew')
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self.lst_msgs = Listbox(self.frame, background=self.BG_COLOR)
        self.lst_msgs.grid(row=0, column=0, sticky='nsew')

        self.results_scroll = Scrollbar(self.frame)
        self.results_scroll.grid(row=0, column=1, sticky='ns')
        self.results_scroll.configure(command=self.lst_msgs.yview)
        self.lst_msgs['yscrollcommand'] = self.results_scroll.set

        msgr.send_msg("This is a normal message")
        msgr.send_msg("This is a warning message", logging.WARN)
        msgr.send_msg("This is an error message", logging.ERROR)

    def center(self):
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = w / 2 - size[0] / 2
        y = h / 2 - size[1] / 2
        self.geometry("%dx%d+%d+%d" % (size + (x, y)))

    def toggle_scan(self):
        if self.btn_toggle.cget("text") == "Stop":
            self.btn_toggle.config(text="Stopping..", state=DISABLED)
            self.stop_scan()
        else:
            self.start_scan()
            self.btn_toggle.config(text="Stop")

    def start_scan(self):
        self.scanner = StashScanner()
        self.scan_thread = Thread(target=self.scanner.start)
        self.scan_thread.start()

    def stop_scan(self):
        if self.scan_thread.is_alive():
            self.scanner.stop()
        else:
            self.btn_toggle.config(text="Start", state=NORMAL)
            self.btn_toggle.update_idletasks()

    def set_msglevel(self, event):
        self.msg_level = logging._nameToLevel[self.cmb_msglevel.get().upper()]

    def clear_msgs(self):
        self.lst_msgs.delete(0, END)

    def handle_msgs(self):
        try:
            while True:
                msg = msgr.msg_queue.get_nowait()

                if msg[0] == MsgType.ScanStopped:
                    self.btn_toggle.config(text="Start", state=NORMAL)
                    self.btn_toggle.update_idletasks()
                elif msg[0] == MsgType.UpdateID:
                    id = msg[1]
                    self.lbl_id_value.config(text=id)
                    self.lbl_id_value.update_idletasks()
                elif msg[0] == MsgType.Text:
                    msg_level, text = msg[1:]

                    if msg_level >= self.msg_level or msg_level == logging.NOTSET:
                        self.lst_msgs.insert(END, text)

                        if msg_level == logging.WARN:
                            self.lst_msgs.itemconfigure(END, foreground=self.WARN_COLOR)
                        elif msg_level == logging.ERROR:
                            self.lst_msgs.itemconfigure(END, foreground=self.ERROR_COLOR)
                        else:
                            self.lst_msgs.itemconfigure(END, foreground=self.DEFAULT_COLOR)

                        self.lst_msgs.update_idletasks()
                        self.lst_msgs.see(END)
        except queue.Empty:
            pass

        self.lst_msgs.after(50, self.handle_msgs)

    def on_close(self):
        self.scanner.stop()
        self.destroy()
        # if self.scan_thread.is_alive():
        #     self.scan_thread.join()


if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()
    app.quit()
