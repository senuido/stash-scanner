import queue
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from idlelib.WidgetRedirector import WidgetRedirector
from queue import Queue
from threading import Thread, Lock
from tkinter import *
import tkinter.font as tkfont
# from tkinter import messagebox
from tkinter import messagebox
from tkinter.ttk import *
import PIL.Image, PIL.ImageTk

import logging

import functools

from lib.CurrencyManager import CurrencyInfo
from lib.FilterManager import FiltersInfo
from lib.ItemHelper import ItemInfo, ItemType, PropDisplayMode
from lib.StashScanner import StashScanner
from lib.Utility import MsgType, msgr, getDataFromUrl, round_up

logger = logging.getLogger('ui')


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
    IMG_NAME = 'item_image'

    def __init__(self):

        super().__init__()

        self.msg_level = logging.INFO
        self.msg_tags = {}
        self.ui_queue = Queue()
        self.last_index = -1
        self.lbl_item_img = None
        self.initialized = False
        self.currency_info = CurrencyInfo()
        self.filters_info = FiltersInfo()

        s = Style()
        # print(s.theme_names())
        s.theme_use('vista')

        self.title("Stash Scanner by Senu")
        self.geometry("1024x600")
        self.center()
        self.create_widgets()

        try:
            ItemDisplay.init()
        except IOError as e:
            messagebox.showerror('Resource error',
                                 'Failed to load image resources.\n{}\n'
                                 'Make sure the files are valid and in place.'.format(e))
        except Exception as e:
            messagebox.showerror('Resource error',
                                 'Failed to load image resources.\n Error: {}'.format(e))
        else:
            self.after(100, self.handle_msgs)
            # self.lst_msgs.after(1000, self.handle_ui_msgs)

            self.protocol("WM_DELETE_WINDOW", self.on_close)
            self.scanner = None
            self.scan_thread = None
            self.details_lock = Lock()

            self.start_scan()
            self.initialized = True

    def create_widgets(self):
        self.configure(padx=10, pady=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.upper_frame = Frame(self, relief='groove')
        self.upper_frame.grid(row=0, sticky='nsew', ipadx=5)
        self.upper_frame.columnconfigure(8, weight=1)

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

        self.btn_currency = Button(self.upper_frame, text="Currency Info",
                                   command=lambda: self.update_details(self.currency_info))
        self.btn_currency.grid(row=0, column=4, pady=5, padx=(5, 0), sticky='ns')

        self.btn_filters = Button(self.upper_frame, text="Filters Info",
                                  command=lambda: self.update_details(self.filters_info))
        self.btn_filters.grid(row=0, column=5, pady=5, padx=(5, 0), sticky='ns')

        self.lbl_spacer = Label(self.upper_frame)
        self.lbl_spacer.grid(row=0, column=8)

        self.lbl_id_value = Label(self.upper_frame, text="", foreground="blue")
        self.lbl_id_value.grid(row=0, column=12, padx=(0, 10), sticky='e')

        self.pane_wnd = PanedWindow(self, orient=HORIZONTAL)
        self.pane_wnd.grid(row=1, column=0, sticky='nsew')

        self.lst_msgs = Listbox(self.pane_wnd, background=self.BG_COLOR, selectmode=SINGLE)
        self.lst_msgs.bind('<<ListboxSelect>>', self.lst_selected)

        self.txt_details = ReadOnlyText(self.pane_wnd, background=self.DETAILS_BG_COLOR, foreground=self.DEFAULT_COLOR,
                                        padx=20, name='txt_details')
        self.pane_wnd.add(self.lst_msgs, weight=1)
        # self.pane_wnd.add(self.txt_details)

        # self.results_scroll = Scrollbar(self.frame)
        # self.results_scroll.grid(row=0, column=1, sticky='nsew')
        # self.results_scroll.configure(command=self.lst_msgs.yview)
        # self.lst_msgs['yscrollcommand'] = self.results_scroll.set

        font_fam = self.findfont(self.FONTS)
        # print('Using font family: {}'.format(font_fam))
        font_default = tkfont.Font(name='DetailsDefault', family=font_fam, size=9)
        font_bold = tkfont.Font(name='DetailsBold', family=font_fam, size=9, weight=tkfont.BOLD)
        font_title = tkfont.Font(name='DetailsTitle', family=font_fam, size=13, weight=tkfont.BOLD)
        font_title_big = tkfont.Font(name='DetailsTitleBig', family=font_fam, size=15, weight=tkfont.BOLD)
        font_tag_big = tkfont.Font(name='DetailsTagBig', family=font_fam, size=12, weight=tkfont.BOLD)
        font_tag = tkfont.Font(name='DetailsTag', family=font_fam, size=9, weight=tkfont.BOLD)
        font_subtext = tkfont.Font(name='DetailsSubtext', family=font_fam, size=8)
        font_underline = tkfont.Font(name='DetailsUnderline', family=font_fam, size=9, underline=True)
        font_tiny = tkfont.Font(name='DetailsTiny', family=font_fam, size=5)
        font_bold_italic = tkfont.Font(name='DetailsBoldItalic', family=font_fam, weight=tkfont.BOLD, slant=tkfont.ITALIC, size=9)

        self.txt_details.configure(font=font_default)

        # self.txt_details.tag_configure(self.type_tags[ItemType.Normal], foreground=self.NORMAL_COLOR, font='-weight bold')
        #### ITEM TAGS

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

        self.txt_details.tag_configure('title', font=font_title_big)
        self.txt_details.tag_configure('subtitle', font=font_bold_italic)

        self.txt_details.tag_configure('corrupted', foreground=self.CORRUPTED_COLOR, background=self.CORRUPTED_BGCOLOR,
                                       font=font_tag_big)

        self.txt_details.tag_configure('enchanted', foreground=self.ENCHANTED_COLOR, background=self.ENCHANTED_BGCOLOR,
                                       font=font_tag)

        self.txt_details.tag_configure('crafted', foreground=self.CRAFTED_COLOR, background=self.CRAFTED_BGCOLOR,
                                       font=font_tag)

        self.txt_details.tag_configure('implicit', font=font_underline)

        self.txt_details.tag_configure('requirement', foreground=self.REQ_COLOR, font=font_subtext)
        self.txt_details.tag_configure('bold', font=font_bold)
        self.txt_details.tag_configure('unid', foreground=self.UNID_COLOR, font=font_bold)
        self.txt_details.tag_configure('tiny', foreground=self.REQ_COLOR, font=font_tiny)
        self.txt_details.tag_configure('justified', justify=CENTER)


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

        # msgr.send_msg("This is a normal message")
        # msgr.send_msg("This is a warning message", logging.WARN)
        # msgr.send_msg("This is an error message", logging.ERROR)

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
        w = event.widget
        index = int(w.curselection()[0])
        # value = w.get(index)

        if index == self.last_index:
            return

        # if any(self.txt_details.winfo_name() in child for child in self.pane_wnd.panes()):
            # self.pane_wnd.forget(self.txt_details)

        if index in self.msg_tags:
            self.last_index = index
            self.update_details(self.msg_tags[index])

    def update_details(self, obj):
        if isinstance(obj, ItemDisplay):
            # print('updating details: {}'.format(obj.item.name))
            self.update_details_item(obj)
        elif isinstance(obj, CurrencyInfo):
            self.update_details_currency(obj)
        elif isinstance(obj, FiltersInfo):
            self.update_details_filters(obj)

        if not any(self.txt_details.winfo_name() in child for child in self.pane_wnd.panes()):
            self.pane_wnd.add(self.txt_details)

    def update_details_filters(self, obj):
        if not isinstance(obj, FiltersInfo):
            return

        self.clear_details()
        details = self.txt_details

        details.configure(padx=40)
        details.insert(END, '\n')
        details.insert(END, 'Active Filters\n', ('justified', 'title'))

        if obj.filters is None:
            details.insert(END, '\n', 'title')
            details.insert(END, 'Filters weren\'t loaded yet.\nStart a scan and try again.\n', 'justified')
            return

        details.insert(END, 'Loaded {} filters, {} are active\n\n'.format(obj.n_loaded, obj.n_active),
                       ('justified', 'subtitle'))

        # tabs = round_up(max(len(name) for name in obj.filters) / self.TK_TABWIDTH)
        # tabs = max(tabs, 1)

        for fltr in obj.filters:
            details.insert(END, fltr + '\n')

    def update_details_currency(self, obj):
        if not isinstance(obj, CurrencyInfo):
            return

        self.clear_details()
        details = self.txt_details

        details.configure(padx=40)
        details.insert(END, '\n')
        details.insert(END, 'Currency Rates\n\n', ('justified', 'title'))

        if obj.rates is None:
            details.insert(END, 'Currency rates weren\'t loaded yet.\nStart a scan and try again.\n', 'justified')
            return

        tabs = round_up(max(len(curr) for curr in obj.rates) / self.TK_TABWIDTH)
        tabs = max(tabs, 1)

        for curr in sorted(obj.rates, key=lambda x: obj.rates[x], reverse=True):
            rate = obj.rates[curr]
            if int(rate) != rate:
                rate = round(rate, 3)
            details.insert(END, '{}:{}{}\n'.format(curr, '\t'*tabs, rate))

        if obj.last_update:
            details.insert(END, '\nLast update: \t{}'.format(obj.last_update.strftime('%I:%M %p - %d, %b %Y')))

    def update_details_item(self, obj):
        if not isinstance(obj, ItemDisplay):
            return

        if not obj.image:
            obj.downloadImages()

        self.clear_details()
        details = self.txt_details
        item = obj.item

        details.configure(padx=20)

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

        if item.enchant or item.implicit:
            for mod in item.enchant:
                details.insert(END, 'enchanted', 'enchanted')
                details.insert(END, " {}\n".format(mod))
            for mod in item.implicit:
                if item.identified:
                    details.insert(END, "{}\n".format(mod), 'implicit')
                else:
                    details.insert(END, "{}\n".format(mod))

        if not item.identified:
            details.insert(END, 'Unidentified\n', 'unid')
        elif item.explicit or item.crafted:
            for mod in item.explicit:
                details.insert(END, "{}\n".format(mod))
            for mod in item.crafted:
                details.insert(END, 'crafted', 'crafted')
                details.insert(END, " {}\n".format(mod))

        props = ''
        if item.properties:
            if item.enchant or item.implicit or item.explicit or item.crafted or not item.identified:
                details.insert(END, '\n'*3, 'tiny')

            tabbed_props = [prop for prop in item.properties
                            if prop['displayMode'] != PropDisplayMode.Format and prop.get('values')]

            if len(tabbed_props) <= 1:
                tabs = 0
            else:
                # prop_lengths = [len(prop['name']) if prop['displayMode'] != PropDisplayMode.Format and prop.get('values')
                #                 else 0 for prop in item.properties]
                prop_lengths = [len(prop['name']) for prop in tabbed_props]
                tabs = max(round_up(max(prop_lengths) / self.TK_TABWIDTH), 2)

            spacing = '\t' * tabs if tabs else ' '
            for prop in sorted(item.properties, key=lambda x: x['displayMode']):
                if props:
                    props += '\n'
                if prop.get('values'):
                    # PropDisplayMode logic here
                    if prop['displayMode'] == PropDisplayMode.Progress:
                        # props += '{}:{spacing}{}% ({})'.format(prop['name'], round(prop['progress']*100),
                        #                                        prop['values'][0][0], spacing=spacing)
                        props += '{}:{spacing}{}%'.format(prop['name'], round(prop['progress'] * 100), spacing=spacing)
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

        if item.duplicated:
            if not props:
                details.insert(END, '\n')
            details.insert(END, 'Mirrored\n', 'bold')

        # if item.sockets:
        #     if props or item.enchant or item.implicit or item.explicit or item.crafted or not item.identified:
        #         details.insert(END, '\n')
        #     other = 'Sockets:\t{}\n'.format(item.sockets)
        #
        #     links = item.links_string.replace('G', '<white>{W}')
        #     links = links.replace('S', '<red>{R}')
        #     links = links.replace('D', '<green>{G}')
        #     links = links.replace('I', '<blue>{B}')
        #
        #     other += 'Links:\t{}\t{}\n'.format(item.links, links)
        #
        #     details.insert(END, other)

        details.highlight_tags()

        details.insert(END, '\n'*2, 'tiny')
        self.lbl_item_img = Label(self.txt_details, background=self.DETAILS_BG_COLOR, image=obj.image_overlay)
        if item.sockets:
            self.lbl_item_img.bind('<Enter>', functools.partial(self.update_item_img, img=obj.image))
            self.lbl_item_img.bind('<Leave>', functools.partial(self.update_item_img, img=obj.image_overlay))

        img_index = '{}.0'.format(int(float(details.index(END))) - 1)
        details.window_create(END, window=self.lbl_item_img)

        details.tag_add('justified', img_index, END)

        return details

    def clear_details(self):
        with self.details_lock:
            self.txt_details.delete(1.0, END)

            # cannot configure img label after text delete is called because
            # it deletes the embedded window which is this label's parent
            self.lbl_item_img = None

    def clear_msgs(self):
        self.lst_msgs.delete(0, END)
        self.last_index = -1
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
                            if isinstance(tag, ItemInfo):
                                item = ItemDisplay(tag, msgr.msg_queue)
                                item.downloadImages()
                                self.msg_tags[self.lst_msgs.size() - 1] = item
                            else:
                                self.msg_tags[self.lst_msgs.size() - 1] = tag
                        if msg_level == logging.WARN:
                            self.lst_msgs.itemconfigure(END, foreground=self.WARN_COLOR)
                        elif msg_level == logging.ERROR:
                            self.lst_msgs.itemconfigure(END, foreground=self.ERROR_COLOR)
                        else:
                            self.lst_msgs.itemconfigure(END, foreground=self.DEFAULT_COLOR)

                        self.lst_msgs.update_idletasks()
                        self.lst_msgs.see(END)
                elif msg[0] == MsgType.Object:
                    obj = msg[1]
                    if isinstance(obj, CurrencyInfo):
                        self.currency_info = obj
                    elif isinstance(obj, FiltersInfo):
                        self.filters_info = obj
                    elif isinstance(obj, ItemDisplay):
                        # selected = self.lst_msgs.curselection()
                        # if selected:
                        curItem = self.msg_tags.get(self.last_index)
                        if curItem and curItem is obj:
                            # print('Updating image: {}'.format(obj.item.name))
                            self.update_item_img(img=obj.image_overlay)
        except queue.Empty:
            pass

        self.after(50, self.handle_msgs)

    # def handle_ui_msgs(self):
    #     try:
    #         while True:
    #             obj = self.ui_queue.get_nowait()
    #             if isinstance(obj, ItemDisplay):
    #                 selected = self.lst_msgs.curselection()
    #                 if selected:
    #                     curItem = self.msg_tags.get(int(selected[0]))
    #                     if curItem and curItem is obj:
    #                         self.txt_details.image_configure(self.IMG_NAME, image=obj.image)
    #                         print('WE NEED TO UPDATE THE VIEWED ITEM WITH THE COOL NEW IMAGES')
    #                         # do stuff to text widget
    #     except queue.Empty:
    #         pass
    #
    #     self.after(200, self.handle_ui_msgs)

    def on_close(self):
        self.scanner.stop()
        self.destroy()
        # if self.scan_thread.is_alive():
        #     self.scan_thread.join()

    def update_item_img(self, evt=None, img=None):
        with self.details_lock:
            if self.lbl_item_img:
                self.lbl_item_img.config(image=img)



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


class ItemDisplay:
    CACHE = {}
    thread_pool = ThreadPoolExecutor(max_workers=16)

    @classmethod
    def init(cls):
        cls.red = PIL.Image.open('res\\str.png')
        cls.blue = PIL.Image.open('res\\int.png')
        cls.green = PIL.Image.open('res\\dex.png')
        cls.white = PIL.Image.open('res\\gen.png')
        cls.link_vertical = PIL.Image.open('res\\link_vertical.png')
        cls.link_horizontal = PIL.Image.open('res\\link_horizontal.png')

        cls.s_height = cls.red.width
        cls.s_width = cls.red.height

    def __init__(self, item, ui_queue):
        self.item = item
        self.image = None
        self.image_overlay = None
        self.ui_queue = ui_queue  # we use this queue to inform UI thread when the item changes
        self.requested = False

    def downloadImages(self):
        if self.requested or self.image:
            return

        if self.item.icon in self.CACHE:
            self.onDownloadComplete(self.item.icon, self.CACHE[self.item.icon])
        else:
            # print('Requesting Img: {}'.format(self.item.name))

            # worker = Thread(target=getDataFromUrl, args=(self.item.icon, self.onDownloadComplete, 5), daemon=True)
            # worker.start()
            self.thread_pool.submit(getDataFromUrl, self.item.icon, self.onDownloadComplete, max_attempts=5)

    def onDownloadComplete(self, url, data):
        self.requested = False
        if not data:
            # print('Request Failed: {}'. format(self.item.name))
            return
        if self.image:
            return

        # CONVERT DATA TO GIF IMAGE
        try:
            img = PIL.Image.open(data)
            self.image = PIL.ImageTk.PhotoImage(img)
            self.updateOverlayImage(img)

            if url not in self.CACHE:
                self.CACHE[url] = data

            # notify ui
            self.ui_queue.put((MsgType.Object, self))
        except OSError as e:
            with open('tmp\\{}.err.png'.format(self.item.name.strip()), mode='wb') as f:
                f.write(data.getvalue())
            logger.error('Image conversion failed: {}, Length: {}\t{}'.format(self.item.name, len(data.getvalue()), url))

    def updateOverlayImage(self, item_image):
        if not self.item.sockets:
            self.image_overlay = self.image
            return

        base_img = item_image.copy()

        w = self.item.w
        h = self.item.h

        sockets = (len(self.item.links_string) + 1) / 2
        n_line_sockets = min(w, sockets)
        n_col_sockets = min(h, round_up(sockets / w))

        # socket start position
        sx = round(base_img.width / 2 - n_line_sockets * self.s_width / 2)
        sy = round(base_img.height / 2 - n_col_sockets * self.s_height / 2)
        socket_list = []

        for i, color in enumerate(re.split('[- ]', self.item.links_string)):
            socket_index = i % w
            line_index = int(i / w)

            if line_index % 2 == 0:
                pos = (sx + self.s_width * socket_index, sy + self.s_height * line_index)
            else:
                pos = (sx + self.s_width * (w - 1 - socket_index), sy + self.s_height * line_index)

            if color == 'S':
                socket_type = self.red
            elif color == 'D':
                socket_type = self.green
            elif color == 'I':
                socket_type = self.blue
            else:
                socket_type = self.white

            base_img.paste(socket_type, pos, socket_type)

            socket_list.append((pos, socket_type))

        for i, link in enumerate(filter(lambda x: x, re.split('[^- ]', self.item.links_string))):
            if link == ' ':
                continue

            curr_x, curr_y = socket_list[i][0]
            next_x, next_y = socket_list[i + 1][0]
            line_index = int((i + 1) / w)

            if curr_y == next_y:
                if line_index % 2 == 0:
                    pos = (round(curr_x + self.s_width - self.link_horizontal.width / 2),
                           round(curr_y + self.s_height / 2 - self.link_horizontal.height / 2))
                else:
                    pos = (round(next_x + self.s_width - self.link_horizontal.width / 2),
                           round(next_y + self.s_height / 2 - self.link_horizontal.height / 2))

                link_type = self.link_horizontal
            else:
                pos = (round(curr_x + self.s_width / 2 - self.link_vertical.width / 2),
                       round(curr_y + self.s_height - self.link_vertical.height / 2))
                link_type = self.link_vertical

            socket_list.append((pos, link_type))

        for item in socket_list:
            pos, img = item
            base_img.paste(img, pos, img)

        self.image_overlay = PIL.ImageTk.PhotoImage(base_img)


if __name__ == "__main__":
    app = AppGUI()

    if app.initialized:
        app.mainloop()

    app.quit()
