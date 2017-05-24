import queue
from queue import Queue
from threading import Thread
from tkinter import *
from tkinter.ttk import *

from lib.StashScanner import StashScanner, LogLevel, MsgType, ControlMsg


class AppGUI(Tk):

    def __init__(self):

        super().__init__()

        self.title("Stash Scanner")
        self.geometry("1024x600")
        self.center()
        self.create_widgets()

        self.msg_queue = Queue()
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

        self.btn_info = Button(self.upper_frame, text="Info", command=self.set_log_info)
        self.btn_info.grid(row=0, column=0, padx=(5, 0), pady=5, sticky='ns')
        self.btn_norm = Button(self.upper_frame, text="Normal", command=self.set_log_normal)
        self.btn_norm.grid(row=0, column=1, pady=5, sticky='ns')
        self.btn_clear = Button(self.upper_frame, text="Clear", command=self.clear_msgs)
        self.btn_clear.grid(row=0, column=2, pady=5, sticky='ns')

        #self.lbl_id = Label(self.upper_frame, text="Change ID:")
        #self.lbl_id.grid(row=0, column=5, padx=(30, 0), sticky='e')

        self.lbl_id_value = Label(self.upper_frame, text="", foreground="blue")
        self.lbl_id_value.grid(row=0, column=6, padx=(0, 10), sticky='e')

        self.btn_toggle = Button(self.upper_frame, text="Stop", command=self.toggle_scan)
        self.btn_toggle.grid(row=0, column=3, pady=5, sticky='ns')
        # self.btn_dbg = Button(self.upper_frame, text="Debug", command=self.set_log_debug, )
        # self.btn_dbg.grid(row=0, column=4, pady=5, sticky='ns')

        self.frame = Frame(self, relief='sunken')
        self.frame.grid(row=1, column=0, sticky='nsew')
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self.lst_msgs = Listbox(self.frame)
        self.lst_msgs.grid(row=0, column=0, sticky='nsew')

        self.results_scroll = Scrollbar(self.frame)
        self.results_scroll.grid(row=0, column=1, sticky='ns')
        self.results_scroll.configure(command=self.lst_msgs.yview)
        self.lst_msgs['yscrollcommand'] = self.results_scroll.set

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
            # self.msg_queue.put(("Stopping!", MsgType.Text))
        else:
            self.start_scan()
            self.btn_toggle.config(text="Stop")

    def start_scan(self):
        self.scanner = StashScanner(self.msg_queue)
        self.scan_thread = Thread(target=self.scanner.start)
        self.scan_thread.start()

    def stop_scan(self):
        self.scanner.stop()
        # self.scan_thread.join()

    def set_log_normal(self):
        self.scanner.set_log_level(LogLevel.Undefined)

    def set_log_info(self):
        self.scanner.set_log_level(LogLevel.Info)

    def set_log_debug(self):
        self.scanner.set_log_level(LogLevel.Debug)

    def clear_msgs(self):
        self.lst_msgs.delete(0, END)
        self.scanner.set_log_level(LogLevel.Error)

    def handle_msgs(self):
        try:
            while True:
                msg, msg_type = self.msg_queue.get_nowait()
                if msg_type == MsgType.Control:
                    if msg[0] == ControlMsg.Stopped:
                        self.btn_toggle.config(text="Start", state=NORMAL)
                        self.btn_toggle.update_idletasks()
                    elif msg[0] == ControlMsg.UpdateID:
                        self.lbl_id_value.config(text=msg[1])
                        self.lbl_id_value.update_idletasks()
                elif msg_type >= MsgType.Text:
                    self.lst_msgs.insert(END, msg)
                    if msg_type == MsgType.TextError:
                        self.lst_msgs.itemconfigure(END, foreground='red')
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

app = AppGUI()

app.mainloop()

app.quit()
