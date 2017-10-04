import copy
import functools
import os
import pprint
import threading
from enum import Enum
from tkinter import Toplevel, StringVar, BooleanVar, messagebox, IntVar
from tkinter.constants import *
import tkinter.font as tkfont
from tkinter.ttk import Notebook, Frame, Label, Button, Style, Combobox, Entry, Checkbutton, Scale, LabelFrame

from lib.CurrencyManager import cm
from lib.FilterManager import fm
from lib.ItemFilter import Filter
from lib.Utility import logexception, AppException, config, AppConfiguration, ConfidenceLevel
from ui.MyTreeview import EditableTreeview
from ui.ScrollingFrame import AutoScrollbar
from ui.TooltipEntry import TooltipEntry
from ui.cmb_autocomplete import Combobox_Autocomplete
from ui.entry_placeholder import PlaceholderEntry
from ui.ttk_spinbox import Spinbox

READONLY = 'readonly'

ColEntry = EditableTreeview.ColEntry

TAB_FPRICES = 'fprices'
TAB_CURRENCY = 'currency'

INVALID_PRICE = 'Price format is: <amount> <currency>\nExamples: 100 chaos, 20 ex, 5 divine'
INVALID_PRICE_OVERRIDE = 'Price format is: <amount> <currency>\nExamples: 100 chaos, 20 ex, 5 divine\n' \
                         'Prices can also be relative to their base.\n' \
                         'Examples: / 3, * 0.5, +2.5 ex, -20 chaos'

# class ConfigEditor(Toplevel):


class ConfigEditor(Notebook):
    def __init__(self, master, app_main, **kwargs):
        super().__init__(master, **kwargs)

        # style = Style()
        # if we do this we also need to hide the #0 column because it adds indention for possible children
        # style.configure("Treeview.Heading", padding=(10, 0))

        # self.protocol('WM_DELETE_WINDOW', self.onClose)
        # self.nb_tabs = Notebook(self)

        # self.create_iprice_tab()
        self.prices_editor = PricesEditor(self)
        self.currency_editor = CurrencyEditor(self)
        self.settings_editor = SettingsEditor(self, app_main)
        # self.add(self.frm_iprices_tab, text='Item Prices', sticky='nsew')

        self.add(self.settings_editor, text='General', sticky='nsew')
        self.add(self.prices_editor, text='Prices', sticky='nsew')
        self.add(self.currency_editor, text='Currency', sticky='nsew')
        self.bind('<<NotebookTabChanged>>', self.onTabChange)

        self.settings_editor_id, self.prices_tab_id, self.currency_tab_id = self.tabs()

    def loadCurrency(self, force=False):
        self.currency_editor.loadCurrency(force_reload=force)

    def loadPrices(self, force=False):
        self.prices_editor.loadPrices(force_reload=force)

    def loadSettings(self):
        self.settings_editor.loadSettings()

    def onTabChange(self, event=None):
        current_tab_id = self.select()
        if current_tab_id == self.currency_tab_id:
            self.loadCurrency(force=True)
        elif current_tab_id == self.prices_tab_id:
            self.loadPrices(force=True)
        elif current_tab_id == self.settings_editor_id:
            self.loadSettings()
    # def onClose(self):
    #     self.destroy()

leagueOptions = [
    'Harbinger',
    'Hardcore Harbinger',
    'Standard',
    'Hardcore',
    # 'Beta Standard',
    # 'Beta Hardcore'
]

scanModeOptions = ['Latest', 'Continue']

class SettingsEditor(Frame):
    def __init__(self, master, app_main, **kwargs):
        super().__init__(master, **kwargs)

        self.app = app_main
        self.create_settings_ui()

    def create_settings_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.frm_settings = Frame(self)
        # self.frm_settings.rowconfigure(2, weight=1)
        # self.frm_settings.columnconfigure(0, weight=1)

        is_valid_req_delay = self.register(functools.partial(_is_number, min=0))
        is_valid_duration = self.register(functools.partial(_is_number, min=0, max=20))
        is_valid_history_retention = self.register(functools.partial(_is_number, min=0, max=100))
        is_valid_max_conns = self.register(functools.partial(_is_number, min=1, max=20, integer=True))
        is_valid_num_workers = self.register(functools.partial(_is_number, min=0, max=os.cpu_count() or 8, integer=True))

        self.frm_settings.grid(padx=10, pady=10, sticky='nsew')

        frm_basic = LabelFrame(self.frm_settings, text='Basic')
        frm_basic.grid(padx=5, pady=5, sticky='nsew', row=0, column=0, ipadx=5)

        lbl = Label(frm_basic, text='League:')
        lbl.grid(row=0, column=0, padx=5, pady=3, sticky='w')
        self.cmb_league = Combobox(frm_basic, state=READONLY, values=leagueOptions)
        self.cmb_league.grid(row=0, column=1, pady=3, sticky='nsew')
        # lbl = Label(frm_basic, text='Minimum request delay(s):')
        # lbl.grid(row=1, column=0, padx=5, pady=3, sticky='w')
        # self.entry_req_delay = Entry(frm_basic, validate='all', validatecommand=(is_valid_req_delay, '%P'))
        # self.entry_req_delay.grid(row=1, column=1, pady=3, sticky='nsew')
        # lbl = Label(frm_basic, text='Scan mode:')
        # lbl.grid(row=2, column=0, padx=5, pady=3, sticky='w')
        # self.cmb_scan_mode = Combobox(frm_basic, state=READONLY, values=scanModeOptions)
        # self.cmb_scan_mode.grid(row=2, column=1, pady=3, sticky='nsew')
        lbl = Label(frm_basic, text='Notification duration(s):')
        lbl.grid(row=3, column=0, padx=5, pady=3, sticky='w')

        self.entry_notification_duration = Entry(frm_basic, validate='all',
                                                 validatecommand=(is_valid_duration, '%P'))
        self.entry_notification_duration.grid(row=3, column=1, pady=3, sticky='nsew')

        frm = LabelFrame(self.frm_settings, text='Advanced')
        frm.grid(pady=5, sticky='nsew', row=0, column=1, ipadx=5)

        lbl = Label(frm, text='Scan mode:')
        lbl.grid(row=0, column=0, padx=5, pady=3, sticky='w')
        self.cmb_scan_mode = Combobox(frm, state=READONLY, values=scanModeOptions)
        self.cmb_scan_mode.grid(row=0, column=1, pady=3, sticky='nsew')

        lbl = Label(frm, text='Min. request delay:')
        lbl.grid(row=1, column=0, padx=5, pady=3, sticky='w')
        self.entry_req_delay = Entry(frm, validate='all', validatecommand=(is_valid_req_delay, '%P'))
        self.entry_req_delay.grid(row=1, column=1, pady=3, sticky='nsew')
        lbl = Label(frm, text='(seconds)')
        lbl.grid(row=1, column=2, padx=(5, 0), pady=3, sticky='w')

        lbl = Label(frm, text='Max connections:')
        lbl.grid(row=2, column=0, padx=5, pady=3, sticky='w')
        self.entry_max_conns = Entry(frm, validate='all', validatecommand=(is_valid_max_conns, '%P'))
        self.entry_max_conns.grid(row=2, column=1, pady=3, sticky='nsew')

        lbl = Label(frm, text='Parsers #:')
        lbl.grid(row=3, column=0, padx=5, pady=3, sticky='w')
        self.entry_num_workers = Entry(frm, validate='all', validatecommand=(is_valid_num_workers, '%P'))
        self.entry_num_workers.grid(row=3, column=1, pady=3, sticky='nsew')
        lbl = Label(frm, text='(0 = Auto)')
        lbl.grid(row=3, column=2, padx=(5, 0), pady=3, sticky='w')

        lbl = Label(frm, text='History retention:')
        lbl.grid(row=4, column=0, padx=5, pady=3, sticky='w')
        self.entry_history_retention = Entry(frm, validate='all', validatecommand=(is_valid_history_retention, '%P'))
        self.entry_history_retention.grid(row=4, column=1, pady=3, sticky='nsew')
        lbl = Label(frm, text='(days)')
        lbl.grid(row=4, column=2, padx=(5, 0), pady=3, sticky='w')

        frm = Frame(frm_basic)
        frm.grid(row=4, column=0)

        self.var_notify = BooleanVar()
        self.var_notify.trace_variable('w', lambda a, b, c: self._on_notify_option_change())
        self.cb_notifications = Checkbutton(frm, text='Growl notifications', variable=self.var_notify)
        self.cb_notifications.grid(row=0, column=0, padx=5, pady=3, sticky='w')

        self.var_notify_copy = BooleanVar()
        self.cb_notify_copy = Checkbutton(frm, text='Copy message', variable=self.var_notify_copy)
        self.cb_notify_copy.grid(row=1, column=0, padx=5, pady=3, sticky='w')

        self.var_notify_play_sound = BooleanVar()
        self.cb_notify_play_sound = Checkbutton(frm, text='Play sound', variable=self.var_notify_play_sound)
        self.cb_notify_play_sound.grid(row=2, column=0, padx=5, pady=3, sticky='w')

        frm_btns = Frame(self.frm_settings)
        frm_btns.grid(row=2, columnspan=3, pady=(20, 5), sticky='w')

        self.btn_apply = Button(frm_btns, text='Apply', command=self.applyChanges)
        self.btn_apply.grid(row=0, column=0, padx=5)
        self.btn_reload = Button(frm_btns, text='Reload', command=self.loadSettings)
        self.btn_reload.grid(row=0, column=1)

    def _on_notify_option_change(self):
        state = NORMAL if self.var_notify.get() else DISABLED
        self.cb_notify_copy.config(state=state)
        self.cb_notify_play_sound.config(state=state)

    def applyChanges(self):
        cfg = AppConfiguration()

        cfg.league = self.cmb_league.get() or leagueOptions[0]
        cfg.notify = self.var_notify.get()
        cfg.notify_copy_msg = self.var_notify_copy.get()
        cfg.notify_play_sound = self.var_notify_play_sound.get()
        cfg.notification_duration = float(self.entry_notification_duration.get() or 4)
        cfg.request_delay = float(self.entry_req_delay.get() or 0.7)
        cfg.scan_mode = self.cmb_scan_mode.get() or scanModeOptions[0]

        cfg.history_retention = int(self.entry_history_retention.get() or 1)
        cfg.max_conns = int(self.entry_max_conns.get() or 8)
        cfg.num_workers = int(self.entry_num_workers.get() or 0)
        cfg.smooth_delay = config.smooth_delay

        self.app.update_configuration(cfg)

    def loadSettings(self):
        self.cmb_league.set(config.league)
        self.cmb_scan_mode.set(config.scan_mode)
        self.entry_notification_duration.delete(0, END)
        self.entry_notification_duration.insert(0, config.notification_duration)
        self.var_notify.set(config.notify)
        self.var_notify_copy.set(config.notify_copy_msg)
        self.var_notify_play_sound.set(config.notify_play_sound)
        self.entry_req_delay.delete(0, END)
        self.entry_req_delay.insert(0, config.request_delay)

        self.entry_history_retention.delete(0, END)
        self.entry_history_retention.insert(0, config.history_retention)
        self.entry_max_conns.delete(0, END)
        self.entry_max_conns.insert(0, config.max_conns)
        self.entry_num_workers.delete(0, END)
        self.entry_num_workers.insert(0, config.num_workers)


class CurrencyColumn(Enum):
    Currency = 'Currency'
    Rate = 'Rate'
    Override = 'Override'
    EffectiveRate = 'Effective Rate'
    Filler = ''

currencyColumns = [col.name for col in CurrencyColumn]

class PricesColumn(Enum):
    Name = 'Name'
    ID = 'ID'
    ItemPrice = 'Item value'
    Override = 'Override'
    FilterPrice = 'Effective item value'#'Filter Price (c)'
    FilterOverride = 'Filter Override'
    EffectiveFilterPrice = 'Effective Filter Price (c)'
    FilterStateOverride = 'Filter State Override'
    Filler = ''

pricesColumns = [col.name for col in PricesColumn]

class FilterStateOption(Enum):
    Enable = True
    Disable = False

filterStateOptions = [''] + [option.name for option in FilterStateOption]

class PricesEditor(Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.create_prices_ui()
        self.initial_values = {}
        self.table_modified = False

    def create_prices_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.frm_prices = Frame(self)
        self.frm_prices.rowconfigure(2, weight=1)
        self.frm_prices.columnconfigure(0, weight=1)
        self.frm_prices.grid(padx=10, pady=10, sticky='nsew')

        # Button Frame
        frm_btns = Frame(self.frm_prices, relief=SOLID, borderwidth=2)
        frm_btns.grid(row=0, column=0, pady=(0, 5), sticky='nsew')
        frm_btns.columnconfigure(10, weight=1)
        # self.entry_currency = \
        #     Combobox_Autocomplete(frm, list_of_items=['one of many currencies'], startswith_match=False)

        self.search_var = StringVar()
        self.entry_search = PlaceholderEntry(frm_btns, 'Search..',
                                             style='Default.TEntry', textvariable=self.search_var)

        self.search_var.trace_variable('w', lambda a, b, c: self.tree.search(self.entry_search.get_value()))
        self.entry_search.bind('<Return>',
                               lambda event: self.tree.search(self.entry_search.get_value(), find_next=True))
        self.btn_apply = Button(frm_btns, text='Apply', command=self.applyChanges)
        self.btn_reload = Button(frm_btns, text='Reload', command=lambda: self.loadPrices(force_reload=True))

        self.entry_search.grid(row=2, column=0, pady=5, padx=5)
        self.btn_apply.grid(row=2, column=2, pady=5)
        # frm.columnconfigure(3, weight=1)
        self.btn_reload.grid(row=2, column=3, sticky='e', pady=5)

        self.var_advanced = BooleanVar(False)
        self.var_advanced.trace_variable('w', lambda a, b, c: self._on_view_option_change())
        self.cb_advanced = Checkbutton(frm_btns, text='Advanced', variable=self.var_advanced)
        self.cb_advanced.grid(row=2, column=10, sticky='e', padx=10)

        frm_border = Frame(self.frm_prices, relief=SOLID, borderwidth=2)
        frm_border.grid(row=2, column=0, sticky='nsew')
        frm_border.rowconfigure(2, weight=1)
        frm_border.columnconfigure(0, weight=1)
        # Tree Frame
        self.frm_tree = Frame(frm_border)
        self.frm_tree.grid(row=2, column=0, sticky='nsew', padx=5, pady=(0, 0))
        self.frm_tree.rowconfigure(0, weight=1)
        self.frm_tree.columnconfigure(0, weight=1)

        self.tree = EditableTreeview(self.frm_tree, on_cell_update=self.onCellUpdate)
        scrly = AutoScrollbar(self.frm_tree, command=self.tree.yview)
        scrlx = AutoScrollbar(self.frm_tree, command=self.tree.xview, orient=HORIZONTAL)
        self.tree.config(yscrollcommand=scrly.set, xscrollcommand=scrlx.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrly.grid(row=0, column=1, sticky='nsew')
        scrlx.grid(row=1, column=0, sticky='nsew')

        # Button Frame
        frm = Frame(frm_border) #, relief=SOLID, borderwidth=1)
        # frm = Frame(self.frm_prices)
        frm.grid(row=0, column=0, sticky='nsew')
        # self.entry_currency = \
        #     Combobox_Autocomplete(frm, list_of_items=['one of many currencies'], startswith_match=False)

        lbl = Label(frm, text='Item value threshold:')
        lbl.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.var_threshold = StringVar()
        self.entry_threshold = TooltipEntry(frm, textvariable=self.var_threshold)
        self.entry_threshold.bind('<FocusOut>', lambda event: self._validate_threshold_entry())
        self.entry_threshold.grid(row=0, column=1, padx=5, pady=5)
        self.var_threshold.trace('w', lambda a, b, c: self.on_entry_change(self.entry_threshold))

        lbl = Label(frm, text='Budget:')
        lbl.grid(row=0, column=2, padx=5, pady=5)
        self.var_budget = StringVar()
        self.entry_budget = TooltipEntry(frm, textvariable=self.var_budget)
        self.entry_budget.bind('<FocusOut>', lambda event: self._validate_budget_entry())
        self.entry_budget.grid(row=0, column=3, padx=5, pady=5)
        self.var_budget.trace('w', lambda a, b, c: self.on_entry_change(self.entry_budget))

        lbl = Label(frm, text='Minimum price:')
        lbl.grid(row=0, column=4, padx=5, pady=5)
        self.var_min_price = StringVar()
        self.entry_min_price = TooltipEntry(frm, textvariable=self.var_min_price)
        self.entry_min_price.bind('<FocusOut>', lambda event: self._validate_min_price_entry())
        self.entry_min_price.grid(row=0, column=5, padx=5, pady=5)
        self.var_min_price.trace('w', lambda a, b, c: self.on_entry_change(self.entry_min_price))

        lbl = Label(frm, text='Default filter override:')
        lbl.grid(row=0, column=6, padx=5, pady=5)
        self.lbl_fprice_override = lbl
        self.var_fprice_override = StringVar()
        self.entry_fprice_override = TooltipEntry(frm, textvariable=self.var_fprice_override)
        self.entry_fprice_override.bind('<FocusOut>', lambda event: self._validate_fprice_override_entry())
        self.entry_fprice_override.grid(row=0, column=7, padx=5, pady=5)
        self.var_fprice_override.trace('w', lambda a, b, c: self.on_entry_change(self.entry_fprice_override))

        # Advanced

        lbl = Label(frm, text='Default item value override:')
        lbl.grid(row=1, column=0, padx=5, pady=(2, 5), sticky='w')
        self.lbl_price_override = lbl
        self.var_price_override = StringVar()
        self.entry_price_override = TooltipEntry(frm, textvariable=self.var_price_override)
        self.entry_price_override.bind('<FocusOut>', lambda event: self._validate_price_override_entry())
        self.entry_price_override.grid(row=1, column=1, padx=5, pady=(2, 5))
        self.var_price_override.trace('w', lambda a, b, c: self.on_entry_change(self.entry_price_override))

        # Confidence Level
        lbl = Label(frm, text="Confidence level:")
        lbl.grid(row=1, column=2, padx=5, pady=(2, 5), sticky='w')
        self.lbl_confidence_lvl = lbl
        self.var_confidence_lvl = IntVar()
        self.entry_confidence_lvl = ConfidenceScale(frm, variable=self.var_confidence_lvl)
        self.entry_confidence_lvl.grid(row=1, column=3, padx=5, pady=(2, 5))
        self.var_confidence_lvl.trace('w', lambda a, b, c: self.on_entry_change(self.entry_confidence_lvl))

        self.var_5l_filters = BooleanVar(False)
        self.cb_5l_filters = VarCheckbutton(frm, text='Enable 5L filters', variable=self.var_5l_filters)
        self.cb_5l_filters.var = self.var_5l_filters
        self.cb_5l_filters.grid(row=1, column=4, padx=5, pady=(2, 5), columnspan=1)
        self.var_5l_filters.trace_variable('w', lambda a, b, c: self.on_entry_change(self.cb_5l_filters))

        # Tree Config
        tree = self.tree

        def init_tree_column(col):
            col_name = pricesColumns[0] if col == '#0' else col
            tree.heading(col, text=PricesColumn[col_name].value, anchor=W, command=lambda col=col: tree.sort_col(col))
            tree.column(col, width=140, stretch=False)

        # self.tree['columns'] = ('ID', 'Item Price', 'Override', 'Filter Price', 'Filter Override', 'Effective Filter Price', 'Filter State Override', '')
        self.tree['columns'] = pricesColumns[1:]

        self.tree.register_column(PricesColumn.Override.name,
                                  ColEntry(TooltipEntry(self.tree), func_validate=_validate_price_override))
        self.tree.register_column(PricesColumn.FilterOverride.name,
                                  ColEntry(TooltipEntry(self.tree), func_validate=_validate_price_override))
        self.tree.register_column(PricesColumn.FilterStateOverride.name,
                                  ColEntry(Combobox(self.tree, values=filterStateOptions, state=READONLY),
                                           accept_events=('<<ComboboxSelected>>', '<Return>')))

        for col in (('#0', ) + tree['columns']):
            init_tree_column(col)

        tree.heading('#0', anchor=CENTER)
        tree.column('#0', width=200, stretch=False)
        tree.column(PricesColumn.Filler.name, stretch=True)

        tree.heading(PricesColumn.ItemPrice.name,
                     command=lambda col=PricesColumn.ItemPrice.name: tree.sort_col(col, key=self._price_key))
        tree.heading(PricesColumn.Override.name,
                     command=lambda col=PricesColumn.Override.name: tree.sort_col(col, key=self._price_key))
        tree.heading(PricesColumn.FilterOverride.name,
                     command=lambda col=PricesColumn.FilterOverride.name: tree.sort_col(col, key=self._price_key))

        tree.heading(PricesColumn.FilterPrice.name,
                     command=lambda col=PricesColumn.FilterPrice.name: tree.sort_col(col, key=self._rate_key, default=0))
        tree.heading(PricesColumn.EffectiveFilterPrice.name,
                     command=lambda col=PricesColumn.EffectiveFilterPrice.name: tree.sort_col(col, key=self._rate_key, default=0))

        self.bvar_modified = BooleanVar()
        self.bvar_modified.trace('w', lambda a, b, c: self._updateApplyState())
        self.bvar_modified.set(False)
        self.var_advanced.set(False)

    def _rate_key(self, key):
        if key == 'N/A':
            return 0
        return float(key)

    def _price_key(self, key):
        if key == '':
            return None  # this means it will be ignored while sorting
        try:
            return cm.compilePrice(key, base_price=0)
        except Exception:
            return 0

    def on_entry_change(self, entry):
        val = entry.get()

        if self.initial_values[entry] != val:
            self.bvar_modified.set(True)

    # def on_price_entry_focusout(self, widget):
    #     valid = _validate_price(widget, accept_empty=False)
    #     if valid and not self.bvar_modified.get() and self.initial_values[widget] != widget.get():
    #         self.bvar_modified.set(True)
    #     return valid
    #
    # def on_override_entry_focusout(self, widget):
    #     valid = _validate_price_override(widget, accept_empty=False)
    #     if valid and not self.bvar_modified.get() and self.initial_values[widget] != widget.get():
    #         self.bvar_modified.set(True)
    #     return valid

    def _validate_threshold_entry(self):
        return _validate_price(self.entry_threshold, accept_empty=False)

    def _validate_budget_entry(self):
        return _validate_price(self.entry_budget, accept_empty=True)

    def _validate_min_price_entry(self):
        return _validate_price(self.entry_min_price, accept_empty=True)

    def _validate_price_override_entry(self):
        return _validate_price_override(self.entry_price_override, accept_empty=False)

    def _validate_fprice_override_entry(self):
        return _validate_price_override(self.entry_fprice_override, accept_empty=False)

    def _update_modified(self):
        modified = any(entry.get() != self.initial_values[entry] for entry in self.initial_values) or self.table_modified

        self.bvar_modified.set(modified)

    def _updateApplyState(self):
        if self.bvar_modified.get():
            self.btn_apply.config(state=NORMAL)
        else:
            self.btn_apply.config(state=DISABLED)

    def _validateForm(self):
        if not self._validate_threshold_entry():
            return False
        if not self._validate_budget_entry():
            return False
        if not self._validate_min_price_entry():
            return False
        if not self._validate_price_override_entry():
            return False
        if not self._validate_fprice_override_entry():
            return False
        return True

    def applyChanges(self, event=None):
        if not self.bvar_modified.get() or not fm.initialized:
            return
        if not self._validateForm():
            return

        price_threshold = self.entry_threshold.get()
        default_price_override = self.entry_price_override.get()
        default_fprice_override = self.entry_fprice_override.get()
        budget = self.entry_budget.get()
        min_price = self.entry_min_price.get()
        confidence_lvl = self.entry_confidence_lvl.get() or fm.DEFAULT_CONFIDENCE_LEVEL
        enable_5l_filters = self.var_5l_filters.get()


        price_overrides = {}
        filter_price_overrides = {}
        filter_state_overrides = {}

        for iid in self.tree.get_children():
            id = self.tree.set(iid, PricesColumn.ID.name)
            iprice = self.tree.set(iid, PricesColumn.Override.name)

            if iprice:
                price_overrides[id] = iprice

            fprice = self.tree.set(iid, PricesColumn.FilterOverride.name)
            if fprice:
                filter_price_overrides[id] = fprice

            fstate = self.tree.set(iid, PricesColumn.FilterStateOverride.name)
            try:
                filter_state_overrides[id] = FilterStateOption[fstate].value
            except KeyError:
                pass

        ids = set([self.tree.set(iid, PricesColumn.ID.name) for iid in self.tree.get_children()])

        # preserve unhandled ids configuration
        for key in (set(fm.price_overrides) - ids):
            price_overrides[key] = fm.price_overrides[key]

        for key in (set(fm.filter_price_overrides) - ids):
            filter_price_overrides[key] = fm.filter_price_overrides[key]

        for key in (set(fm.filter_state_overrides) - ids):
            filter_state_overrides[key] = fm.filter_state_overrides[key]

        try:
            fm.updateConfig(default_price_override, default_fprice_override, price_threshold, budget, min_price,
                            price_overrides, filter_price_overrides, filter_state_overrides, int(confidence_lvl), enable_5l_filters)
        except AppException as e:
            messagebox.showerror('Validation error',
                                 'Failed to update configuration:\n{}'.format(e), parent=self.winfo_toplevel())
        except Exception as e:
            logexception()
            messagebox.showerror('Update error',
                                 'Failed to apply changes, unexpected error:\n{}'.format(e), parent=self.winfo_toplevel())
        else:
            # SHOULD always work since config is valid, main console will report any failures
            # background thread because schema validating takes a bit of time
            threading.Thread(target=fm.compileFilters).start()
            self._initFormState()

    def loadPrices(self, force_reload=False):
        if not cm.initialized or not fm.initialized:
            return

        if not force_reload:
            self._update_modified()  # in case of reverted changes
            if self.bvar_modified.get():  # dont interrupt user changes
                return

        tree = self.tree
        tree.clear()

        table = {}
        for fltr in fm.autoFilters:
            # effective_rate = cm.crates.get(curr, '')
            # if effective_rate != '':
            #     effective_rate = round(effective_rate, 3)

            fid = fltr.id

            fstate_override = fm.filter_state_overrides.get(fid, '')
            try:
                fstate_override = FilterStateOption(fstate_override).name
            except ValueError:
                fstate_override = ''

            table[fid] = (fltr.title, fid, fm.item_prices[fid], fm.price_overrides.get(fid, ''),
                          _to_display_rate(fm.compiled_item_prices.get(fid, 'N/A')), fm.filter_price_overrides.get(fid, ''),
                          _to_display_rate(fm.compiled_filter_prices.get(fid, 'N/A')), fstate_override)

        for fid in table:
            tree.insert('', END, '', text=table[fid][0], values=table[fid][1:])

        # tree.sort_by('#0', descending=True)
        tree.sort_col('#0', reverse=False)

        self._initFormState()

    # def onItemPriceUpdate(self, iid, col, old, new):
    #     print('IPrice update: iid {}, col {}'.format(iid, col))

    def onCellUpdate(self, iid, col, old, new):
        if old != new:
            self.table_modified = True
            self.bvar_modified.set(True)
            # self._update_modified()

    def _initFormState(self):
        self.table_modified = False
        self.initial_values[self.entry_threshold] = fm.price_threshold
        self.initial_values[self.entry_budget] = fm.budget
        self.initial_values[self.entry_min_price] = fm.default_min_price
        self.initial_values[self.entry_price_override] = fm.default_price_override
        self.initial_values[self.entry_fprice_override] = fm.default_fprice_override
        self.initial_values[self.entry_confidence_lvl] = fm.confidence_level
        self.initial_values[self.cb_5l_filters] = fm.enable_5l_filters

        self.var_threshold.set(fm.price_threshold)
        self.var_budget.set(fm.budget)
        self.var_min_price.set(fm.default_min_price)
        self.var_price_override.set(fm.default_price_override)
        self.var_fprice_override.set(fm.default_fprice_override)
        self.var_confidence_lvl.set(fm.confidence_level)
        self.var_5l_filters.set(fm.enable_5l_filters)

        self.bvar_modified.set(False)

    def _on_view_option_change(self):
        advanced_widgets = [self.entry_price_override, self.lbl_price_override,
                            self.lbl_confidence_lvl, self.entry_confidence_lvl, self.cb_5l_filters]
        if not self.var_advanced.get():
            for w in advanced_widgets:
                w.grid_remove()
            self.tree.config(displaycolumn=[PricesColumn.FilterPrice.name, PricesColumn.FilterOverride.name,
                                            PricesColumn.EffectiveFilterPrice.name, PricesColumn.Filler.name])
        else:
            for w in advanced_widgets:
                w.grid()
            self.tree.config(displaycolumn='#all')
        self.tree.on_entry_close()

class CurrencyEditor(Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.bvar_modified = BooleanVar()
        self.create_currency_ui()

    def create_currency_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.frm_currency = Frame(self)
        self.frm_currency.rowconfigure(2, weight=1)
        self.frm_currency.columnconfigure(0, weight=1)
        self.frm_currency.grid(padx=10, pady=10, sticky='nsew')

        # Tree Frame
        self.frm_tree = Frame(self.frm_currency)
        self.frm_tree.grid(row=2, sticky='nsew')
        self.frm_tree.rowconfigure(0, weight=1)
        self.frm_tree.columnconfigure(0, weight=1)

        self.tree = EditableTreeview(self.frm_tree, on_cell_update=self.onCellUpdate)
        scrly = AutoScrollbar(self.frm_tree, command=self.tree.yview)
        scrlx = AutoScrollbar(self.frm_tree, command=self.tree.xview, orient=HORIZONTAL)
        self.tree.config(yscrollcommand=scrly.set, xscrollcommand=scrlx.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrly.grid(row=0, column=1, sticky='nsew')
        scrlx.grid(row=1, column=0, sticky='nsew')

        self.tree.insert('', 0, text='Exalted Orb', values=('90', '85'))

        frm = Frame(self.frm_currency, relief=SOLID, borderwidth=2)
        frm.columnconfigure(10, weight=1)
        frm.grid(row=1, column=0, pady=(0, 5), sticky='nsew')
        # self.entry_currency = \
        #     Combobox_Autocomplete(frm, list_of_items=['one of many currencies'], startswith_match=False)

        self.search_var = StringVar()
        self.entry_search = PlaceholderEntry(frm, 'Search..',
                                             style='Default.TEntry', textvariable=self.search_var)

        self.search_var.trace_variable('w', lambda a, b, c: self.tree.search(self.entry_search.get_value()))
        self.entry_search.bind('<Return>', lambda event: self.tree.search(self.entry_search.get_value(), find_next=True))
        # self.btn_currency_search = Button(frm, text='Search', command=lambda event: self.tree_currency.search(self.entry_currency_search.get_value(), find_next=True))
        self.btn_apply = Button(frm, text='Apply', command=self.applyChanges)
        self.btn_reload = Button(frm, text='Reload', command=lambda: self.loadCurrency(force_reload=True))

        self.entry_search.grid(row=2, column=0, pady=5, padx=5)
        # self.btn_currency_search.grid(row=2, column=1, pady=5)
        self.btn_apply.grid(row=2, column=2, pady=5)
        # frm.columnconfigure(3, weight=1)
        self.btn_reload.grid(row=2, column=3, sticky='e', pady=5)

        # Confidence Level
        lbl = Label(frm, text="Confidence level:")
        lbl.grid(row=2, column=10, padx=5, sticky='nse', pady=(3, 5))
        self.lbl_confidence_lvl = lbl
        self.var_confidence_lvl = IntVar()
        self.entry_confidence_lvl = ConfidenceScale(frm, variable=self.var_confidence_lvl)
        self.entry_confidence_lvl.grid(row=2, column=11, padx=5, pady=5)
        self.var_confidence_lvl.trace('w', lambda a, b, c: self.on_entry_change(self.entry_confidence_lvl))

        # Tree Config
        tree = self.tree
        tree['columns'] = currencyColumns[1:]
        tree.register_column('Override', ColEntry(TooltipEntry(tree), func_validate=_validate_price_override))

        def init_tree_column(col):
            col_name = currencyColumns[0] if col == '#0' else col
            tree.heading(col, text=CurrencyColumn[col_name].value, anchor=W, command=lambda col=col: tree.sort_col(col))
            tree.column(col, width=140, stretch=False)

        for col in ('#0', ) + tree['columns']:
            init_tree_column(col)

        tree.heading('#0', anchor=CENTER)
        tree.column('#0', width=250, stretch=False)
        tree.column(CurrencyColumn.Filler.name, stretch=True)

        tree.heading(CurrencyColumn.Rate.name,
                     command=lambda col=CurrencyColumn.Rate.name: tree.sort_col(col, key=float, default=0))
        tree.heading(CurrencyColumn.EffectiveRate.name,
                     command=lambda col=CurrencyColumn.EffectiveRate.name: tree.sort_col(col, key=float, default=0))
        tree.heading(CurrencyColumn.Override.name,
                     command=lambda col=CurrencyColumn.Override.name: tree.sort_col(col, key=self._price_key))

        self.bvar_modified.trace('w', lambda a, b, c: self._updateApplyState())

    def _price_key(self, key):
        if key == '':
            return None  # this means it will be ignored while sorting
        try:
            return cm.compilePrice(key, base_price=0)
        except Exception:
            return 0

    def _updateApplyState(self):
        if self.bvar_modified.get():
            self.btn_apply.config(state=NORMAL)
        else:
            self.btn_apply.config(state=DISABLED)

    def loadCurrency(self, force_reload=False):
        if not cm.initialized:
            return
        if not force_reload and self.bvar_modified.get():
            return

        self.var_confidence_lvl.set(cm.confidence_level)

        tree = self.tree
        tree.clear()

        table = {}
        for curr in cm.shorts:
            effective_rate = cm.crates.get(curr, '0')
            table[curr] = (_to_display_rate(cm.rates.get(curr, '')), cm.overrides.get(curr, ''), _to_display_rate(effective_rate))

        for curr in table:
            tree.insert('', END, '', text=curr, values=table[curr])

        tree.sort_col(CurrencyColumn.EffectiveRate.name, key=float, default=0)

        self.bvar_modified.set(False)

    def applyChanges(self, event=None):
        if not self.bvar_modified.get() or not cm.initialized:
            return

        overrides = {}

        for iid in self.tree.get_children():
            #TODO: hide #0 col and move names to a value column
            currency_name_col = '#0' # CurrencyColumn.Currency.name
            # id = self.tree.set(iid, currency_name_col)
            id = self.tree.item(iid, 'text')
            override = self.tree.set(iid, CurrencyColumn.Override.name)

            if override:
                overrides[id] = override

        # ids = set([self.tree.set(iid, currency_name_col) for iid in self.tree.get_children()])
        ids = set([self.tree.item(iid, 'text') for iid in self.tree.get_children()])

        # preserve unhandled ids configuration
        for key in (set(cm.overrides) - ids):
            overrides[key] = cm.overrides[key]

        cm.confidence_level = self.entry_confidence_lvl.get()

        try:
            cm.compile(overrides=overrides)
            if fm.initialized:
                threading.Thread(target=fm.compileFilters).start()
            self.bvar_modified.set(False)
        except AppException as e:
            messagebox.showerror('Update error', e, parent=self.winfo_toplevel())
        except Exception as e:
            logexception()
            messagebox.showerror('Update error',
                                 'Failed to apply changes, unexpected error:\n{}'.format(e),
                                 parent=self.winfo_toplevel())

    def onCellUpdate(self, iid, col, old, new):
        if not self.bvar_modified.get() and old != new:
            self.bvar_modified.set(True)

    def on_entry_change(self, entry):
        self.bvar_modified.set(True)


class VarCheckbutton(Checkbutton):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.var = kw.get('variable', None)

    def configure(self, cnf=None, **kw):
        super().configure(cnf, **kw)
        if 'variable' in kw:
            self.var = kw['variable']

    def get(self):
        if self.var:
            return self.var.get()
        return None


class ConfidenceScale(Frame):
    def __init__(self, master, **kw):
        super().__init__(master)

        # self.grid_propagate(0)
        # self.columnconfigure(0, weight=1)
        # self.rowconfigure(0, weight=1)

        self.var = kw.get('variable', IntVar())
        kw['variable'] = self.var
        kw['from_'] = ConfidenceLevel.Low.value
        kw['to'] = ConfidenceLevel.VeryHigh.value
        # kw['command'] = self.scale_change
        kw['orient'] = HORIZONTAL

        self.lbl_scale = Label(self)
        self.scale = Scale(self, **kw)

        self.scale_font = tkfont.nametofont(Style().lookup('TLabel', 'font')).copy()
        self.scale_font.config(weight=tkfont.BOLD, size=9)
        self.lbl_scale.config(font=self.scale_font, width=3, anchor=CENTER)
        self.var.trace_variable('w', lambda a, b, c: self.scale_change())

        self.scale.grid(row=0, column=0, sticky='ns')
        self.lbl_scale.grid(row=0, column=1, sticky='ns', padx=(3, 0))

    def scale_change(self):
        rval = self.get()

        if rval >= ConfidenceLevel.High:
            fg = '#4CAF50'
        elif rval >= ConfidenceLevel.Medium:
            fg = '#FF9800'
        else:
            fg = '#FF5722'
        self.lbl_scale.config(foreground=fg, text=str(rval))

    def get(self):
        return round(float(self.var.get()))

def _validate_price(widget, accept_empty=True):
    val = widget.get()
    valid, reason = _is_price_valid(val, accept_empty)
    if not valid:
        widget.showTooltip(reason)
        widget.focus()
    else:
        widget.hideTooltip()

    return valid

def _is_price_valid(val, accept_empty=True):
    if accept_empty and val.strip() == '':
        return True, ''
    if not cm.initialized:
        return True, ''
    if not cm.isPriceValid(val):
        return False, INVALID_PRICE
    return True, ''

def _validate_price_override(widget, accept_empty=True):
    val = widget.get()
    valid, reason = _is_price_override_valid(val, accept_empty)
    if not valid:
        widget.showTooltip(reason)
        widget.focus()
    else:
        widget.hideTooltip()

    return valid

def _is_price_override_valid(val, accept_empty=True):
    if accept_empty and val.strip() == '':
        return True, ''
    if not cm.isOverridePriceValid(val):
        return False, INVALID_PRICE_OVERRIDE
    return True, ''

def _to_display_rate(val):
    if val == 'N/A' or val == '':
        return val
    if int(val) == float(val):
        return int(val)
    return round(val, 2)

def _is_number(text, min=None, max=None, accept_empty=True, integer=False):
    try:
        # text = text.strip()
        if text == '':
            return accept_empty

        if text.find(' ') != -1:
            return False

        if integer:
            num = int(text)
        else:
            num = float(text)

        if min is not None and num < min:
            return False
        if max is not None and num > max:
            return False
        return True
    except ValueError:
        return False