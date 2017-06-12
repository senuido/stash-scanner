import idlelib
import pprint
import queue
from idlelib.WidgetRedirector import WidgetRedirector
from queue import Queue
from threading import Thread
from tkinter import *
import tkinter.font as tkfont
from tkinter.ttk import *


import logging

from lib.ItemHelper import ItemInfo, ItemType, PropDisplayMode
from lib.StashScanner import StashScanner
from lib.Utility import MsgType, msgr


class AppGUI(Tk):

    TK_TABWIDTH = 8
    BG_COLOR = '#37474F'#263238'#'#455A64'
    DETAILS_BG_COLOR = '#222'
    DEFAULT_COLOR = '#FFFFFF'#'#ECEFF1'
    WARN_COLOR = '#FDD835'
    ERROR_COLOR = 'red'

    NORMAL_COLOR = '#eee'
    MAGIC_COLOR = '#5050EB'
    RARE_COLOR = '#a3a314'
    UNIQUE_COLOR = '#af6025'
    GEM_COLOR = '#1ba29b'
    CURRENCY_COLOR = '#aa9e82' #'#9c7e38'
    DIV_COLOR = '#c1fcf8' #'#dcd3c3'
    QUEST_COLOR = '#4ae63a'
    PROPHECY_COLOR = '#b54bff' #'#dcd3c3'
    RELIC_COLOR = '#82ad6a'

    IMPLICIT_BGCOLOR = '#65621E'
    CORRUPTED_BGCOLOR = '#C22626'
    CORRUPTED_COLOR = '#fff'
    ENCHANTED_BGCOLOR = '#8B579C'
    ENCHANTED_COLOR = '#fff'
    CRAFTED_BGCOLOR = '#0060BF'
    CRAFTED_COLOR = '#fff'
    REQ_COLOR = '#999'
    UNID_COLOR = '#C22626'

    TT_WHITE_COLOR = '#c8c8c8'
    TT_MAGIC_COLOR = '#8888ff'
    TT_RARE_COLOR = '#ff7'
    TT_UNIQUE_COLOR = '#af6025'
    TT_GEM_COLOR = '#1aa29b'
    TT_CURRENCY_COLOR = '#aa9e82'
    TT_DIV_COLOR = '#c1fcf8'
    TT_PROPHECY_COLOR = '#b54bff'

    TT_DEFAULT_COLOR = '#7f7f7f'
    TT_CORRUPTED_COLOR = '#d20000'
    TT_NORMAL_COLOR = '#fff'  # '#eee'  # Used for map tiers, ilvls, map tags
    TT_AUGMENETED_COLOR = '#8888ff'  # '#eee'  # Used for quality

    TT_SRED_COLOR = '#F44336'
    # '#f00'

    TT_SGREEN_COLOR = '#4CAF50'
    #'#0f0' #'#2ECC2E'

    TT_SBLUE_COLOR = '#2196F3'
    # CRAFTED_BGCOLOR #'#00f' #'#44f'

    TT_SWHITE_COLOR = '#fff'

    type_tags = {
        ItemType.Normal: 'name-normal',
        ItemType.Magic: 'name-magic',
        ItemType.Rare: 'name-rare',
        ItemType.Unique: 'name-unique',
        ItemType.Gem: 'name-gem',
        ItemType.Currency: 'name-currency',
        ItemType.DivinationCard: 'name-div',
        ItemType.QuestItem: 'name-quest',
        ItemType.Prophecy: 'name-prophecy',
        ItemType.Relic: 'name-relic'
    }

    FONTS = ['Segoe UI', 'TkTextFont', 'Arial']#"sans-serif" #"Helvetica",Helvetica,Arial,sans-serif;


    def __init__(self):

        super().__init__()

        self.msg_level = logging.INFO
        self.item_info = StringVar()
        self.msg_tags = {}
        s = Style()
        # print(s.theme_names())
        s.theme_use('vista')

        self.title("Stash Scanner by Senu")
        self.geometry("1024x600")
        self.center()
        self.create_widgets()
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


        self.pane_wnd = PanedWindow(self, orient=HORIZONTAL)
        self.pane_wnd.grid(row=1, column=0, sticky='nsew')

        self.lst_msgs = Listbox(self.pane_wnd, background=self.BG_COLOR, selectmode=SINGLE)
        self.lst_msgs.bind('<<ListboxSelect>>', self.lst_selected)

        self.txt_details = ReadOnlyText(self.pane_wnd, background=self.DETAILS_BG_COLOR, foreground=self.DEFAULT_COLOR,
                                        padx=20, name='txt_details')

        self.pane_wnd.add(self.lst_msgs, weight=3)
        # self.pane_wnd.paneconfig(self.lbl_item, width=120)
        # text="AAAAAAAAAA KAMEHAMEHA")  #text="this is a relatively long message")
        # self.lbl_item.grid(row=0, column=2, sticky='ns')

        # self.results_scroll = Scrollbar(self.frame)
        # self.results_scroll.grid(row=0, column=1, sticky='nsew')
        # self.results_scroll.configure(command=self.lst_msgs.yview)
        # self.lst_msgs['yscrollcommand'] = self.results_scroll.set

        # default_font = tkfont.nametofont('TkTextFont')
        # idlelib.help.findfont()
        #
        # fixed_font = tkfont.nametofont('TkFixedFont')
        # pprint.pprint(fixed_font.actual())
        # print(default_font.name)
        # print(default_font.cget('family'))
        # fixed_font.configure(family=default_font.actual()['family'])


        # self.font_bold = default_font.copy()
        # self.font_bold.config(weight='bold', size=12)
        # self.my_font = tkfont.Font(family='Helvetica', size=12, weight='bold')
        # self.my_font2 = tkfont.Font(family='Verdana', size=12, weight='bold')
        # pprint.pprint(self.txt_details.config())
        # pprint.pprint(default_font.config())
        #
        # pprint.pprint(default_font.actual().get('family'))
        # pprint.pprint(self.my_font.actual())

        font_fam = self.findfont(self.FONTS)
        # print('Using font family: {}'.format(font_fam))
        font_default = tkfont.Font(name='DetailsDefault', family=font_fam, size=9)
        font_title = tkfont.Font(name='DetailsTitle', family=font_fam, size=13, weight=tkfont.BOLD)
        font_tag_big = tkfont.Font(name='DetailsTagBig', family=font_fam, size=12, weight=tkfont.BOLD)
        font_tag = tkfont.Font(name='DetailsTag', family=font_fam, size=9, weight=tkfont.BOLD)
        font_subtext = tkfont.Font(name='DetailsSubtext', family=font_fam, size=8)
        font_underline = tkfont.Font(name='DetailsUnderline', family=font_fam, size=9, underline=True)
        font_tiny = tkfont.Font(name='DetailsTiny', family=font_fam, size=5)
        font_bold_italic = tkfont.Font(name='DetailsBoldItalic', family=font_fam, weight=tkfont.BOLD, slant=tkfont.ITALIC, size=9) #, slant=tkfont.ITALIC)

        self.txt_details.configure(font=font_default)

        # self.txt_details.tag_configure(self.type_tags[ItemType.Normal], foreground=self.NORMAL_COLOR, font='-weight bold')

        #### CUSTOM TAGS

        self.txt_details.tag_configure(self.type_tags[ItemType.Normal], foreground=self.NORMAL_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Magic], foreground=self.MAGIC_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Rare], foreground=self.RARE_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Unique], foreground=self.UNIQUE_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Gem], foreground=self.GEM_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Currency], foreground=self.CURRENCY_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.DivinationCard], foreground=self.DIV_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.QuestItem], foreground=self.QUEST_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Prophecy], foreground=self.PROPHECY_COLOR, font=font_title)
        self.txt_details.tag_configure(self.type_tags[ItemType.Relic], foreground=self.RELIC_COLOR, font=font_title)

        self.txt_details.tag_configure('corrupted', foreground=self.CORRUPTED_COLOR, background=self.CORRUPTED_BGCOLOR,
                                       font=font_tag_big)

        self.txt_details.tag_configure('enchanted', foreground=self.ENCHANTED_COLOR, background=self.ENCHANTED_BGCOLOR,
                                       font=font_tag)

        self.txt_details.tag_configure('crafted', foreground=self.CRAFTED_COLOR, background=self.CRAFTED_BGCOLOR,
                                       font=font_tag)

        self.txt_details.tag_configure('implicit', font=font_underline)

        self.txt_details.tag_configure('requirement', foreground=self.REQ_COLOR, font=font_subtext)
        self.txt_details.tag_configure('unid', foreground=self.UNID_COLOR, font=font_tag)
        self.txt_details.tag_configure('tiny', foreground=self.REQ_COLOR, font=font_tiny)


        #### TEXT TAGS

        self.txt_details.tag_configure('<whiteitem>', foreground=self.TT_WHITE_COLOR)
        self.txt_details.tag_configure('<magicitem>', foreground=self.TT_MAGIC_COLOR)
        self.txt_details.tag_configure('<rareitem>', foreground=self.TT_RARE_COLOR)
        self.txt_details.tag_configure('<uniqueitem>', foreground=self.TT_UNIQUE_COLOR)
        self.txt_details.tag_configure('<gemitem>', foreground=self.TT_GEM_COLOR)
        self.txt_details.tag_configure('<currencyitem>', foreground=self.TT_CURRENCY_COLOR)
        self.txt_details.tag_configure('<divination>', foreground=self.TT_DIV_COLOR)
        self.txt_details.tag_configure('<prophecy>', foreground=self.TT_PROPHECY_COLOR)

        self.txt_details.tag_configure('<default>', foreground=self.TT_DEFAULT_COLOR)
        self.txt_details.tag_configure('<corrupted>', foreground=self.TT_CORRUPTED_COLOR)
        self.txt_details.tag_configure('<normal>', foreground=self.TT_NORMAL_COLOR)
        self.txt_details.tag_configure('<augmented>', foreground=self.TT_AUGMENETED_COLOR)

        self.txt_details.tag_configure('<red>', foreground=self.TT_SRED_COLOR, font=font_bold_italic)
        self.txt_details.tag_configure('<green>', foreground=self.TT_SGREEN_COLOR, font=font_bold_italic)
        self.txt_details.tag_configure('<blue>', foreground=self.TT_SBLUE_COLOR, font=font_bold_italic)
        self.txt_details.tag_configure('<white>', foreground=self.TT_SWHITE_COLOR, font=font_bold_italic)

        msgr.send_msg("This is a normal message")
        msgr.send_msg("This is a warning message", logging.WARN)
        msgr.send_msg("This is an error message", logging.ERROR)

    def findfont(self, names):
        "Return name of first font family derived from names."
        for name in names:
            if name.lower() in (x.lower() for x in tkfont.names(root=self)):
                font = tkfont.Font(name=name, exists=True, root=self)
                return font.actual()['family']
            elif name.lower() in (x.lower()
                                  for x in tkfont.families(root=self)):
                return name

    def center(self):
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = w / 2 - size[0] / 2
        y = h / 2 - size[1] / 2
        self.geometry("{}x{}+{}+{}".format(*size, int(x), int(y)))

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

    def lst_selected(self, event):
        # self.item_info = str(int(self.lst_msgs.curselection()[0]))
        w = event.widget
        index = int(w.curselection()[0])
        value = w.get(index)
        self.item_info.set('You selected item {}:\n"{}"'.format(index, value))

        if any(self.txt_details.winfo_name() in child for child in self.pane_wnd.panes()):
            self.pane_wnd.forget(self.txt_details)

        if index in self.msg_tags:
            self.update_details(self.msg_tags[index])
            self.pane_wnd.add(self.txt_details)

    def update_details(self, item):
        if not isinstance(item, ItemInfo):
            return ''

        details = self.txt_details
        details.delete(1.0, END)

        if item.corrupted:
            details.insert(END, 'corrupted', 'corrupted')
            details.insert(END, ' ')

        type_tag = self.type_tags[item.type] if item.type in self.type_tags else self.type_tags[ItemType.Normal]
        details.insert(END, item.name + '\n', type_tag)

        reqs = ''

        if item.requirements:
            for prop in item.requirements:
                if reqs:
                    reqs += ' - '
                if prop.get('values'):
                    # ValueType logic here
                    reqs += '{}: {}'.format(prop['name'], prop['values'][0][0])
                else:
                    reqs += '{}'.format(prop['name'])

        if item.ilvl:
            if reqs:
                reqs += ' - '
            reqs += 'ilvl: {}'.format(item.ilvl)

        if reqs:
            details.insert(END, reqs+'\n', 'requirement')

        details.insert(END, '\n', 'tiny')
        # details.insert(END, "-"*30 + "\n")

        if item.enchant or item.implicit:
            for mod in item.enchant:
                details.insert(END, 'enchanted', 'enchanted')
                details.insert(END, " {}\n".format(mod))
            for mod in item.implicit:
                if item.identified:
                    details.insert(END, "{}\n".format(mod), 'implicit')
                else:
                    details.insert(END, "{}\n".format(mod))
        # else:
        #     details.insert(END, '\n')

        if not item.identified:
            details.insert(END, 'Unidentified\n', 'unid')
        elif item.explicit or item.crafted:
            for mod in item.explicit:
                details.insert(END, "{}\n".format(mod))
            for mod in item.crafted:
                details.insert(END, 'crafted', 'crafted')
                details.insert(END, " {}\n".format(mod))

            # details.insert(END, "-" * 30 + "\n")

        props = ''
        if item.properties:
            if item.enchant or item.implicit or item.explicit or item.crafted or not item.identified:
                details.insert(END, '\n'*3, 'tiny')
            if len(item.properties) == 1:
                tabs = 0
            else:
                tabs = round(max([len(prop['name']) if prop['displayMode'] != PropDisplayMode.Format else 0
                                  for prop in item.properties]) / self.TK_TABWIDTH)
                tabs = max(tabs, 1)
                #tabs = min(tabs, 4)

            spacing = '\t' * tabs if tabs else ' '
            for prop in item.properties:
                if props:
                    props += '\n'
                if prop.get('values'):
                    # PropDisplayMode logic here
                    if prop['displayMode'] == PropDisplayMode.Progress:
                        props += '{}:{spacing}{}% ({})'.format(prop['name'], round(prop['progress']*100),
                                                               prop['values'][0][0], spacing=spacing)
                    elif prop['displayMode'] == PropDisplayMode.Format:
                        format_string = re.sub('%[0-9]+', '{}', prop['name'])
                        # PropValueType logic here
                        props += format_string.format(*[val[0] for val in prop['values']])
                    else:
                        # PropValueType logic here
                        props += '{}:{spacing}{}'.format(prop['name'], prop['values'][0][0], spacing=spacing)
                else:
                    props += '{}'.format(prop['name'])

            details.insert(END, props + '\n')

        if item.sockets:
            if props or item.enchant or item.implicit or item.explicit or item.crafted or not item.identified:
                details.insert(END, '\n')
            other = 'Sockets:\t{}\n'.format(item.sockets)

            links = item.links_string.replace('G', '<white>{W}')
            links = links.replace('S', '<red>{R}')
            links = links.replace('D', '<green>{G}')
            links = links.replace('I', '<blue>{B}')

            other += 'Links:\t{}\t{}\n'.format(item.links, links)

            details.insert(END, other)

        self.txt_details.highlight_tags()
            # details.insert(END, "{:<10}{}\n".format('Sockets:', item.sockets))
            # details.insert(END, "{:<10}{}\n".format('Links:', item.links))

        # for prop, val in item.properties.items():
        #     details.insert(END, "{}: {}\n".format(prop, val))

        return details

    def clear_msgs(self):
        self.lst_msgs.delete(0, END)
        self.msg_tags.clear()

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
                    msg_level, text, tag = msg[1:]

                    if msg_level >= self.msg_level or msg_level == logging.NOTSET:
                        self.lst_msgs.insert(END, text)
                        if tag:
                            self.msg_tags[self.lst_msgs.size() - 1] = tag
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


class ReadOnlyText(Text):

    REGEX_TAG = re.compile('(<[^<]+>){([^<]+)}')

    def __init__(self, *args, **kwargs):
        Text.__init__(self, *args, **kwargs)
        self.redirector = WidgetRedirector(self)
        self.insert = self.redirector.register("insert", lambda *args, **kw: "break")
        self.delete = self.redirector.register("delete", lambda *args, **kw: "break")

    def highlight_tags(self):
        self.mark_set('matchEnd', 1.0)
        self.mark_set('searchLimit', END)

        # pattern = '<[^<]+>{[^<]+}'
        pattern = self.REGEX_TAG.pattern

        count = IntVar()
        tags = [tag.lower() for tag in self.tag_names()]
        while True:
            index = self.search(pattern, 'matchEnd', 'searchLimit',
                                count=count, regexp=True)
            if index == "": break
            if count.get() == 0: break  # degenerate pattern which matches zero-length strings

            indexEnd = "%s+%sc" % (index, count.get())
            self.mark_set('matchEnd', indexEnd)

            text = self.get(index, 'matchEnd')
            match = self.REGEX_TAG.match(text)
            if match: # should always be true
                tag, newtext = match.groups()
                if tag.lower() in tags:
                    self.delete(index, 'matchEnd')
                    self.insert(index, newtext, tag)


if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()
    app.quit()
