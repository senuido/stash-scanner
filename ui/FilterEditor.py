import collections
import copy
import functools
import threading
import tkinter.font as tkfont
from enum import Enum
from tkinter import *
from tkinter import messagebox
from tkinter.ttk import *

from lib.CurrencyManager import cm
from lib.FilterManager import FilterManager, fm, lower_json
from lib.ItemFilter import Filter
from lib.ModFilter import ModFilter, ModFilterType
from lib.ModFilterGroup import FilterGroupFactory, FilterGroupType, CountFilterGroup
from lib.Utility import AppException
from ui.ModsHelper import mod_helper
from ui.MultiCombobox import MultiCombobox
from ui.MyTreeview import MyTreeview
from ui.ScrollingFrame import Scrolling_Area
from ui.TooltipEntry import TooltipEntry, TIP_BELOW, TIP_ABOVE
from ui.cmb_autocomplete import Combobox_Autocomplete
from ui.entry_placeholder import PlaceholderEntry
from ui.ttk_spinbox import Spinbox


class BoolOption(Enum):
    either = None
    Yes = True
    No = False
READONLY = 'readonly'
boolOptions = [bo.name for bo in BoolOption]
FGTypeOptions = [fg_type.name for fg_type in FilterGroupType]
ModTypeOptions = [mod_type.name for mod_type in ModFilterType]

# ItemTypeOptions = [
#     'Normal',
#     'Magic',
#     'Rare',
#     'Unique',
#     'Gem',
#     'Currency',
#     'Divination Card',
#     'Quest Item',
#     'Prophecy',
#     'Relic',
# ]

ItemTypeOptions = collections.OrderedDict([
    ('Normal', 'normal'),
    ('Magic', 'magic'),
    ('Rare', 'rare'),
    ('Unique', 'unique'),
    ('Gem', 'gem'),
    ('Currency', 'currency'),
    ('Divination Card', 'divination card'),
    ('Quest Item', 'quest item'),
    ('Prophecy', 'prophecy'),
    ('Relic', 'relic')
])

# ItemTypeOptions = []
#     'Normal': 'normal',
#     'Magic': 'magic',
#     'Rare': 'rare',
#     'Unique': 'unique',
#     'Gem': 'gem',
#     'Currency': 'currency',
#     'Divination Card':
#     'Quest Item': 'questitem'
#     'Prophecy': 'prophecy',
#     'Relic': 'relic'
# ]


class FilterGroupWidget(Frame):
    class ModFilterWidget:
        LINE_PAD = 3
        def __init__(self, parent, row, mf=None, custom=False):
            self.parent = parent

            if mf is None:
                self.custom = custom
            else:
                self.custom = mod_helper.isCustom(mf.type, mf.expr)

            self.frm_mod = Frame(parent, style='Borderless.TFrame')
            self.frm_mod.grid(row=row, column=0, padx=5, pady=self.LINE_PAD + 2, sticky='nsew')
            self.frm_mod.columnconfigure(1, weight=1)

            self._createModWidgets()

            self.frm_vals = Frame(parent, style='Borderless.TFrame')
            self.frm_vals.grid(row=row, column=1, sticky='nsew', padx=5, pady=self.LINE_PAD+2)
            self.frm_vals.columnconfigure(0, weight=1)
            self.frm_vals.columnconfigure(1, weight=1)
            self.frm_vals.rowconfigure(0, weight=1)
            self.frm_vals.grid_propagate(0)

            is_number_cmd = self.parent.register(_is_number_or_empty)
            self.entry_min = Entry(self.frm_vals, style='Default.TEntry',
                                   validate='all', validatecommand=(is_number_cmd, '%P'))
            self.entry_min.grid(row=0, column=0, sticky='nsew', pady=0)
            self.entry_max = Entry(self.frm_vals, style='Default.TEntry',
                                   validate='all', validatecommand=(is_number_cmd, '%P'))
            self.entry_max.grid(row=0, column=1, sticky='nsew', pady=0)

            self.btn_remove = Button(parent, text='X', command=self.destroy, width=5)
            self.btn_remove.grid(row=row, column=2, sticky='e', padx=5, pady=self.LINE_PAD)

            self.update(mf)

        def _createModWidgets(self):
            if self.custom:
                self.cmb_mod_type = Combobox(self.frm_mod, values=ModTypeOptions, state=READONLY)
                self.cmb_mod_type.grid(row=0, column=0, sticky='nsew', padx=(0,5))
                self.entry_mod = PlaceholderEntry(self.frm_mod, 'Enter a valid regular expression..', style='Default.TEntry')
            else:
                self.entry_mod = Combobox_Autocomplete(self.frm_mod, style='Autocomplete.TEntry',
                                                       list_of_items=mod_helper.mod_list, startswith_match=False)

            self.entry_mod.bind('<<TrueFocusOut>>', self.validateMod, add='+')
            self.entry_mod.grid(row=0, column=1, sticky='nsew')

        def update(self, mf=None):
            # if isinstance(self.entry_mod, PlaceholderEntry):
            if self.custom:
                self.cmb_mod_type.current(0)
                self.entry_mod.Reset()
            else:
                self.entry_mod.delete(0, END)

            self.entry_min.delete(0, END)
            self.entry_max.delete(0, END)

            if mf:
                if self.custom:
                    self.cmb_mod_type.set(mf.type.name)
                    self.entry_mod.set_value(mf.expr)
                else:
                    self.entry_mod.insert(0, mod_helper.modToText(mf.type, mf.expr))

                if mf.min is not None:
                    self.entry_min.insert(0, int(mf.min) if mf.min == int(mf.min) else mf.min)
                if mf.max is not None:
                    self.entry_max.insert(0, int(mf.max) if mf.max == int(mf.max) else mf.max)

        def validateMod(self, event=None):
            if self.custom:
                mod_text = self.entry_mod.get_value()
                try:
                    re.compile(mod_text)
                except re.error as e:
                    self.entry_mod.showTooltip('Invalid regular expression\nError: {}'.format(e), TIP_ABOVE)
                    return False
            else:
                mod_text = self.entry_mod.get()
                if mod_text and not mod_helper.isPredefined(mod_text):
                    self.entry_mod.showTooltip('Choose a mod from the list or leave the field empty.', TIP_ABOVE)
                    return False

            self.entry_mod.hideTooltip()
            return True

        def toModFilter(self):
            if self.custom:
                mod_type = ModFilterType[self.cmb_mod_type.get()]
                expr = self.entry_mod.get_value()
            else:
                mod_text = self.entry_mod.get()
                # if mod_text and not mod_helper.isPredefined(mod_text):
                #     raise AppException('Illegal choice in mod filter: {}'.format(mod_text))

                mod_type, expr = mod_helper.textToMod(mod_text)

            min_val = self.entry_min.get() if self.entry_min.get() else None
            max_val = self.entry_max.get() if self.entry_max.get() else None

            return ModFilter(mod_type, expr, min_val, max_val)

        def set_state(self, state):
            if self.custom:
                if state == NORMAL:
                    self.cmb_mod_type.config(state=READONLY)
                else:
                    self.cmb_mod_type.config(state=DISABLED)
                self.entry_mod.set_state(state)
            else:
                self.entry_mod.config(state=state)

            self.entry_min.config(state=state)
            self.entry_max.config(state=state)
            self.btn_remove.config(state=state)

        def destroy(self):
            self.frm_mod.destroy()
            self.frm_vals.destroy()
            # self.entry_min.destroy()
            # self.entry_max.destroy()
            self.btn_remove.destroy()
            self.parent.removeMFW(self)

    def __init__(self, parent, fg=None, **kw):
        super().__init__(parent, **kw)
        self.mfws = []

        self.columnconfigure(0, weight=1)
        # self.columnconfigure(0, minsize=700)
        self.columnconfigure(1, minsize=120)
        # self.columnconfigure(2, minsize=100)

        self.frm_btns = Frame(self)
        self.btn_add_mod = Button(self.frm_btns, text='Add mod', command=self.addMFW)
        self.btn_add_mod.grid(row=0, column=0)
        self.btn_add_custom = Button(self.frm_btns, text='Add custom', command=lambda: self.addMFW(custom=True))
        self.btn_add_custom.grid(row=0, column=1)

        self.frm_fgtype = Frame(self)
        self.lbl_match = Label(self.frm_fgtype, text='Match type:')
        self.lbl_match.grid(row=0, column=0)
        self.cmb_type = Combobox(self.frm_fgtype, values=FGTypeOptions, state=READONLY)
        self.cmb_type.grid(row=0, column=1)

        self.frm_fgvals = Frame(self)
        self.frm_fgvals.columnconfigure(0, weight=1)
        self.frm_fgvals.columnconfigure(1, weight=1)
        self.frm_fgvals.rowconfigure(0, weight=1)
        self.frm_fgvals.grid_propagate(0)
        self.entry_min = Entry(self.frm_fgvals, style='Default.TEntry')
        self.entry_min.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)
        self.entry_max = Entry(self.frm_fgvals, style='Default.TEntry')
        self.entry_max.grid(row=0, column=1, sticky='nsew', padx=0, pady=0)

        self.btn_remove = Button(self, text='X', command=self.destroy, width=5)

        self.sep = Separator(self)

        self.updateGrid(0)
        self.update(fg)
        if fg is None or len(fg.mfs) == 0:
            self.addMFW()

        # smoother add?
        # row = 0
        # for mf in fg.mfs:
        #     mfw = FilterGroupWidget.ModFilterWidget(self, mf)
        #     self.mfws.append(mfw)
        #     row = row + 1
        #
        # self.updateGrid(len(self.mfws))

    def addMFW(self, mf=None, custom=False):
        max_col, max_row = self.grid_size()
        self.updateGrid(max_row-2)

        mfw = FilterGroupWidget.ModFilterWidget(self, max_row-3, mf, custom)
        self.mfws.append(mfw)

    # used to push all widgets after mod filters one row down
    def updateGrid(self, row):
        self.sep.grid(row=row+2, column=0, columnspan=5, pady=10, padx=5, sticky='nsew')
        self.frm_fgtype.grid(row=row+1, column=0, sticky='w', padx=5)
        self.frm_fgvals.grid(row=row+1, column=1, sticky='nsew', padx=5, pady=2)
        self.btn_remove.grid(row=row+1, column=2, sticky='e', padx=5)
        self.frm_btns.grid(row=row, column=0, columnspan=4, pady=5)

    def update(self, fg=None):
        self.entry_min.delete(0, END)
        self.entry_max.delete(0, END)
        self.cmb_type.current(0)

        if fg:
            self.cmb_type.set(fg.getType().name)
            if isinstance(fg, CountFilterGroup):
                if fg.match_min:
                    self.entry_min.insert(0, str(fg.match_min))
                if fg.match_max:
                    self.entry_max.insert(0, str(fg.match_max))
            for mf in fg.mfs:
                self.addMFW(mf)

    def removeMFW(self, mfw):
        self.mfws.remove(mfw)

    def toFilterGroup(self):
        fg_type = FilterGroupType[self.cmb_type.get()]
        data = {}
        if self.entry_min.get():
            data['match_min'] = int(self.entry_min.get())
        if self.entry_max.get():
            data['match_max'] = int(self.entry_max.get())

        fg = FilterGroupFactory.create(fg_type, data)
        for mfw in self.mfws:
            mf = mfw.toModFilter()
            if mf.expr:
                fg.mfs.append(mf)

        # if isinstance(fg, CountFilterGroup):
        #     if self.entry_min.get():
        #         fg.match_min = self.entry_min.get()
        #     if self.entry_max.get():
        #         fg.match_max = self.entry_max.get()

        return fg

    def set_state(self, state):
        for mfw in self.mfws:
            mfw.set_state(state)

        if state == NORMAL:
            self.cmb_type.config(state=READONLY)
        else:
            self.cmb_type.config(state=DISABLED)

        self.entry_min.config(state=state)
        self.entry_max.config(state=state)
        self.btn_remove.config(state=state)

        self.btn_add_mod.config(state=state)
        self.btn_add_custom.config(state=state)

class FilterEditor(Toplevel):

    _INIT_ERROR = 0
    _INIT_SUCCESS = 1

    def __init__(self, parent):
        Toplevel.__init__(self, parent)

        self.withdraw()
        self.protocol('WM_DELETE_WINDOW', self.onClose)
        self.title('Filter Editor')
        # self.iconbitmap('res\\app.ico')

        # ui_style = Style()
        # # ui_style.configure('Default.TEntry', background='white', highlightbackground="#bebebe", highlightthickness=1, bd=1)
        # ui_style.configure('Default.TEntry', padding=1)
        # ui_style.configure('Placeholder.Default.TEntry', foreground='grey')
        # ui_style.configure('Autocomplete.TEntry') #, borderwidth=0, highlightthickness=1)

        self.positions = {}
        self.filter_form = FormHelper()
        self.fm = fm
        self.currFilter = None
        self.selected = None
        self.objToTreeId = {}  # Obj to tree id
        self.treeIdToObj = {}  # Tree id to Obj
        self.compiling = BooleanVar(False)
        self.compiling.trace('w', lambda a, b, c: self._onCompilingChange())
        self.reload_needed = False

        self.lst_categories = []
        self.lst_ids = []

        self.configure(padx=10, pady=10)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, minsize=250)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(3, weight=1)

        self.frm_tree = Frame(self, style='Borderless.TFrame')
        self.frm_tree.grid(row=0, column=1, sticky='nsew', padx=(0, 5))
        self.frm_tree.columnconfigure(1, weight=1)
        self.frm_tree.rowconfigure(2, weight=1)

        self.frm_tree_btns_border = Frame(self.frm_tree, relief=SOLID, borderwidth=2)
        self.frm_tree_btns_border.grid(row=0, column=0, columnspan=2, sticky='nsew', ipadx=5, ipady=5)

        self.frm_tree_btns_border.rowconfigure(0, weight=1)
        self.frm_tree_btns_border.columnconfigure(0, weight=1)
        self.frm_tree_btns = Frame(self.frm_tree_btns_border)
        self.frm_tree_btns.grid(row=0, column=0)
        self.frm_tree_btns.columnconfigure(0, weight=1)
        self.frm_tree_btns.columnconfigure(1, weight=1)
        self.frm_tree_btns.columnconfigure(2, weight=1)

        self.btn_new = Button(self.frm_tree_btns, text='New', command=self.addNewFilter)
        self.btn_new.grid(row=0, column=0, sticky='nsew')
        self.btn_delete = Button(self.frm_tree_btns, text='Delete', command=self.deleteFilter)
        self.btn_delete.grid(row=0, column=1, sticky='nsew')
        self.btn_copy = Button(self.frm_tree_btns, text='Copy', command=self.copyFilter)
        self.btn_copy.grid(row=0, column=2, sticky='nsew')

        self.search_var = StringVar()
        self.entry_tree_search = PlaceholderEntry(self.frm_tree, 'Search filter..', style='Default.TEntry', textvariable=self.search_var)
        self.entry_tree_search.grid(row=1, column=0, columnspan=2, pady=5, sticky='nsew')
        # self.entry_tree_search.bind('<KeyRelease>', lambda event: self.filterTreeview(self.entry_tree_search.get_value()))

        self.vscroll_tree = Scrollbar(self.frm_tree)
        self.vscroll_tree.grid(row=2, column=0, sticky='ns')
        self.tree = MyTreeview(self.frm_tree, selectmode=BROWSE, yscrollcommand=self.vscroll_tree.set, show='tree')
        self.vscroll_tree.config(command=self.tree.yview)
        self.tree.grid(row=2, column=1, sticky='nsew')
        self.tree.bind('<<TreeviewSelect>>', self.tree_selected)
        self.tree_default_font = tkfont.Font(name=Style().lookup("Treeview", "font"), exists=True)
        self.tree_italic_font = self.tree_default_font.copy()
        self.tree_italic_font.config(slant=tkfont.ITALIC)

        self.search_var.trace_variable('w', lambda a, b, c: self.tree.search(self.entry_tree_search.get_value()))
        self.entry_tree_search.bind('<Return>', lambda event: self.tree.search(self.entry_tree_search.get_value(), find_next=True))

        self.tree.bind('<KeyPress>', self.on_tree_key)

        self.tree.tag_configure('orphan', foreground='red')
        self.tree.tag_configure('error', foreground='red')
        self.tree.tag_configure('circular', foreground='red')
        self.tree.tag_configure('duplicate', foreground='red')
        self.tree.tag_configure('readonly', foreground='grey', font=self.tree_italic_font)

        self.frm_filter = Frame(self)
        self.frm_filter.grid(row=0, column=2, sticky='nsew')
        # self.frm_filter.columnconfigure(0, weight=1)
        self.frm_filter.rowconfigure(2, weight=1)
        # self.frm_filter.rowconfigure(2, weight=1)

        self.lfrm_filter = LabelFrame(self.frm_filter, text='General')
        self.lfrm_filter.grid(row=1, column=0, sticky='nsew')
        self.lfrm_filter.columnconfigure(0, minsize=90)

        self.lfrm_crit = LabelFrame(self.frm_filter, text='Criteria')
        self.lfrm_crit.grid(row=2, column=0, sticky='nsew')
        self.lfrm_crit.columnconfigure(0, minsize=90)

        # self.frm_gap = Frame(self.frm_filter, style='Borderless.TFrame')
        # self.frm_gap.grid(row=2, column=0, sticky='nsew')
        # self.frm_gap.bind("<Configure>", self.frm_fgs_container_configure)

        self.frm_btns_border = Frame(self.frm_filter, relief=SOLID, borderwidth=2)
        self.frm_btns_border.grid(row=3, column=0, sticky='nsew', ipadx=5, ipady=5, pady=(5, 0))
        self.frm_btns_border.rowconfigure(0, weight=1)
        self.frm_btns_border.columnconfigure(0, weight=1)
        self.frm_btns = Frame(self.frm_btns_border)
        self.frm_btns.grid(row=0, column=0, padx=5)
        self.btn_save = Button(self.frm_btns, text='Save', command=self.saveFilter, underline=0)
        self.btn_save.grid(row=0, column=0)
        self.btn_discard = Button(self.frm_btns, text='Discard', command=self.discardFilterChanges)
        self.btn_discard.grid(row=0, column=1)
        self.btn_reset = Button(self.frm_btns, text='Reset', command=self.resetFilter)
        self.btn_reset.grid(row=0, column=2)

        self.bind('<Control-s>', lambda event: self.saveFilter())

        self.createFilterGeneral()
        self.createFilterCriteria()
        self.setFormState(DISABLED)
        self.center()

        # self.init_error = None
        #
        # ls = LoadingScreen(self)
        # # ls.lift()
        #
        # # threading.Thread(target=self.init, args=(ls, )).start()
        # self.wait_window(ls)
        #
        # self.focus_set()
        # self.lift()
        #
        # if self.init_error:
        #     title, message = self.init_error
        #     messagebox.showerror(title, message, parent=self)
        #     self.onClose()
        #     return

        self._update_categories()
        self._update_ids()
        self.fillTree()

        self.deiconify()
        self.wait_visibility()

        try:
            mod_helper.load()
        except Exception as e:
            messagebox.showerror('Mods error',
                                 'Failed to load item mods information.\n{}'.format(e),
                                 parent=self)

        self.tree.selection_set(list())

    def center(self):
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        size = tuple(int(_) for _ in self.geometry().split('+')[0].split('x'))
        x = w / 2 - size[0] / 2
        y = h / 2 - size[1] / 2
        self.geometry("{}x{}+{}+{}".format(*size, int(x), int(y)))

    def on_tree_key(self, event):
        if not self.entry_tree_search:
            return

        # print('char {}, repr \'{}\''.format(event.char, repr(event.char)))

        # if event.char.isalnum() or event.char.isspace():
        if event.char.isalnum():
            self.entry_tree_search.focus_set()
            self.entry_tree_search.insert_value(END, event.char)

    # def init(self, ls):
    #     # if not isinstance(ls, LoadingScreen):
    #     #     return
    #
    #     try:
    #         ls.updateStatus('Loading currency information', 0)
    #         cm.load()
    #
    #         if cm.needUpdate:
    #             try:
    #                 ls.updateStatus('Downloading currency information', 10)
    #                 cm.update()
    #             except AppException as e:
    #                 pass
    #
    #         if not cm.initialized:
    #             self.init_error = ('Currency error', 'Failed to load currency information.')
    #             ls.close()
    #             return
    #
    #         ls.updateStatus('Loading filter configuration', 40)
    #         fm = FilterManager(validate=False)
    #
    #         filterFallback = True
    #
    #         ls.updateStatus('Loading filters', 50)
    #         try:
    #             fm.loadAutoFilters(validate=False)
    #         except AppException as e:
    #             # self.init_error = ('Filters error',
    #             #                    'Failed to load user/generated filters.\n{}'.format(e))
    #             # ls.close()
    #             filterFallback = True
    #
    #         if fm.needUpdate or filterFallback:
    #             try:
    #                 ls.updateStatus('Generating filters from API', 55)
    #                 fm.fetchFromAPI()
    #             except AppException as e:
    #                 self.init_error = ('Filters error', '{}'.format(e))
    #                 ls.close()
    #                 return
    #
    #         try:
    #             ls.updateStatus('Loading user filters', 80)
    #             fm.loadUserFilters(validate=False)
    #         except AppException as e:
    #             self.init_error = ('Filter error',
    #                                '{}'.format(e))
    #             ls.close()
    #             return
    #
    #         self.fm = fm
    #
    #         ls.updateStatus('Loading mods', 90)
    #         try:
    #             mod_helper.load()
    #         except Exception as e:
    #             self.init_error = ('Mods error',
    #                                'Failed to load item mods information.\n{}'.format(e))
    #             ls.close()
    #             return
    #
    #         ls.updateStatus('Initializing..', 95)
    #         self._update_categories()
    #         self._update_ids()
    #         self.init_error = None
    #         ls.close()
    #     except Exception as e:
    #         self.init_error = ('Initialization error', 'Unexpected error occurred while initializing:\n{}'.format(e))
    #         ls.close()

    # def loadFilters(self):
    #
    #     cm.load()
    #     # if cm.initialized:
    #     #     msgr.send_msg("Currency information loaded successfully.", logging.INFO)
    #
    #     try:
    #         cm.update()
    #         # msgr.send_msg("Currency rates updated successfully.")
    #     except AppException as e:
    #         pass
    #         # msgr.send_msg(e, logging.ERROR)
    #         # if cm.initialized:
    #         #     msgr.send_msg('Using currency information from a local copy..', logging.WARN)
    #
    #     if not cm.initialized:
    #         # raise AppException("Failed to load currency information.")
    #         messagebox.showerror('Currency erorr',
    #                              'Failed to load currency information.',
    #                              parent=self)
    #         return False
    #
    #     fm = FilterManager(validate=False)
    #
    #     try:
    #         fm.loadAutoFilters(validate=False)
    #         fm.loadUserFilters(validate=False)
    #         self.fm = fm
    #     except AppException as e:
    #         # self.grab_set()
    #         messagebox.showerror('Filters error',
    #                              'Failed to load user/generated filters.\n{}\n'
    #                              'Start a scan and try again.'.format(e),
    #                              parent=self)
    #         return False
    #
    #     self._update_categories()
    #     self._update_ids()
    #
    #     # try:
    #     #     msgr.send_msg("Generating filters from API..")
    #     #     fm.fetchFromAPI()
    #     # except AppException as e:
    #     #     filterFallback = True
    #     #     msgr.send_msg(e, logging.ERROR)
    #
    #     return True

    def saveFilter(self):
        if self.currFilter is None or self.compiling.get():
            return
        if not self.validateForm():
            return

        data = self.filter_form.form_serialize()
        # pprint.pprint(data)
        data = lower_json(data)
        # pprint.pprint(data)
        # data = lower_json(json.dumps(data, indent=4, cls=FilterEncoder))

        if self.currFilter in self.fm.autoFilters:
            pass
        elif self.currFilter in self.fm.userFilters:
            fltr = Filter.fromDict(data)
            try:
                fltr.validate()
            except AppException as e:
                messagebox.showerror('Validation failed',
                                     'Filter validation failed: {}'.format(e),
                                     parent=self)
                return

            filters = list(self.fm.getRawFilters())
            filters.remove(self.currFilter)
            filters.append(fltr)

            if not self._validate_baseid_not_circular(fltr, filters):
                return

            index = self.fm.userFilters.index(self.currFilter)
            self.fm.userFilters[index] = fltr

            self.applyChanges()

            self.updateTreeFilter(fltr, self.currFilter)
            self.currFilter = fltr

        self._update_categories()
        self._update_ids()

    def _validate_baseid_not_circular(self, fltr, filters):
        start_filter = fltr
        path = [fltr]

        while fltr.isChild:
            fltr = FilterManager.getFilterById(fltr.baseId, filters)
            if fltr is None:
                break  # unable to validate chain because of missing parent
            if FilterManager.getFilterById(fltr.id, path):
                circular_path = path[path.index(FilterManager.getFilterById(fltr.id, path)):]
                if start_filter in circular_path:
                    self.entry_baseid.showTooltip('Circular reference between filters: {}'.format([flt.title or flt.id for flt in circular_path]))
                    return False
                return True  # allow editing filter when it's ancestors are responsible for the circular references

            path.append(fltr)
        return True

    def _update_ids(self):
        self.lst_ids.clear()
        self.lst_ids.extend(sorted(fm.getFilterIds()))

    def _update_categories(self):
        self.lst_categories.clear()
        self.lst_categories.extend(sorted(fm.getCategories()))

    def copyFilter(self):
        if self.currFilter is None or self.compiling.get():
            return

        fltr = self.currFilter
        fltr = copy.deepcopy(fltr)
        fltr.title = "Copy of " + fltr.title
        fltr.id = ''

        self.fm.userFilters.append(fltr)
        self.fm.saveUserFilters()

        self.addFilterToTree(fltr, index=0)
        self.tree.selection_set(self.objToTreeId[fltr])
        self.tree.see(self.objToTreeId[fltr])

    def addNewFilter(self):
        if self.compiling.get():
            return

        fltr = Filter('My filter')

        self.fm.userFilters.append(fltr)
        self.fm.saveUserFilters()

        self.addFilterToTree(fltr, index=0)
        self.tree.selection_set(self.objToTreeId[fltr])
        self.tree.see(self.objToTreeId[fltr])

    def deleteFilter(self, fltr=None):
        if fltr is None:
            if self.currFilter is None:
                return
            fltr = self.currFilter

        if fltr in self.fm.autoFilters or self.compiling.get():
            return

        self.fm.userFilters.remove(fltr)

        self.applyChanges()

        curr_iid = self.objToTreeId[fltr]
        self.onFilterIdChange(curr_iid, new_id=None)

        next_selection = self.tree.next(curr_iid)
        if not next_selection:
            next_selection = self.tree.prev(curr_iid)
        if not next_selection:
            next_selection = self.tree.parent(curr_iid)
        if not next_selection:
            next_selection = list()

        self.tree.delete(curr_iid)

        del self.treeIdToObj[curr_iid]
        del self.objToTreeId[fltr]
        self.tree.selection_set(next_selection)

        self._update_categories()
        self._update_ids()

    def applyChanges(self):
        self.compiling.set(True)
        threading.Thread(target=self._applyChanges).start()

    def _applyChanges(self):
        fm.compileFilters()
        self.fm.saveUserFilters()
        self.compiling.set(False)

    # def onFiltersUpdated(self):
    #     pass
    #
    # def onFiltersCompiled(self):
    #     self.compiling = False
    #     pass
    def onFiltersUpdated(self):
        self.reload_needed = True

    def onFilterIdChange(self, curr_iid=None, new_id=None):
        tree = self.tree

        # children follow parent
        # move one up
        # move children to root - currently doing this
        if curr_iid:
            children = tree.get_children(curr_iid)
            for i, child in enumerate(children):
                tree.move(child, '', i)
                tree.tag_add('orphan', child)

        # move matching orphans under
        if new_id:
            # find orphans
            for child in tree.get_children(''):
                child_fltr = self.treeIdToObj[child]
                if child_fltr.baseId == new_id and curr_iid != child:  # additional check prevents trying to move item under itself
                    tree.move(child, curr_iid, END)
                    tree.tag_remove('orphan', child)

    def updateTreeFilter(self, new, old):
        if new is old:
            return

        tree = self.tree
        curr_iid = self.objToTreeId[old]
        if tree.tag_has('circular') or tree.tag_has('duplicate'):
            self.fillTree()
            tree.selection_set(self.objToTreeId[new])
            tree.see(self.objToTreeId[new])
            return

        del self.objToTreeId[old]
        del self.treeIdToObj[curr_iid]

        last_parent = tree.parent(curr_iid)
        last_index = tree.index(curr_iid)
        tree.detach(curr_iid)

        # we only ever save filters that passed validation
        tree.tag_remove('error', curr_iid)

        # Update item to appear under parent
        if not new.baseId or new.baseId == new.id:
            parent_iid = ''
            tree.tag_remove('orphan', curr_iid)
        else:
            parent_filter = FilterManager.getFilterById(new.baseId, self.objToTreeId)
            if parent_filter is None:
                tree.tag_add('orphan', curr_iid)
                parent_iid = ''
            else:
                tree.tag_remove('orphan', curr_iid)
                parent_iid = self.objToTreeId[parent_filter]

        if last_parent == parent_iid:
            index = last_index
        else:
            index = 0

        tree.move(curr_iid, parent_iid, index)

        # Update tree maps with new obj
        self.objToTreeId[new] = curr_iid
        self.treeIdToObj[curr_iid] = new

        # Update children to appear under parent
        if new.id != old.id:
            self.onFilterIdChange(curr_iid, new.id)

        if new.title != old.title:
            tree.item(curr_iid, text=new.title)

        tree.see(curr_iid)

    def discardFilterChanges(self):
        if self.currFilter is None:
            return
        self.filter_form.form_update(self.currFilter.toDict())

    def resetFilter(self):
        self.filter_form.form_reset()

    def addFilterToTree(self, fltr, lookup=None, index=END):
        if fltr in self.objToTreeId:
            return

        if lookup is None:
            lookup = []

        curr = fltr
        parent = curr.baseId if curr.isChild else None
        # parent = None if not curr.baseId or curr.baseId == curr.id else curr.baseId
        path = [curr]
        circular_path = None

        b_circular = False
        b_orphan = False

        while parent and not b_orphan and not b_circular:
            base_filter = FilterManager.getFilterById(parent, lookup)

            if base_filter is None:
                # Missing parent
                b_orphan = True
            else:
                curr = base_filter
                path.append(curr)
                parent = curr.baseId if curr.isChild else None
                # parent = '' if not curr.baseId or curr.baseId == curr.id else curr.baseId

                if parent and FilterManager.getFilterById(parent, path):
                    # Circular reference detected
                    b_circular = True
                    # print('circular path: ', [fltr.title for fltr in path])
                    circular_path = path[path.index(FilterManager.getFilterById(parent, path)):]
                    # print('minimal circular path: ', [fltr.title for fltr in circular_path])

        parent_filter = None
        for curr in reversed(path):
            if curr in self.objToTreeId:
                parent_filter = curr
                continue

            tags = []
            if curr in self.fm.autoFilters:
                tags.append('readonly')
            else:
                try:
                    curr.validate()
                except AppException:
                    tags.append('error')

            if parent_filter is None:
                if curr.isChild:
                # if curr.baseId and curr.baseId != curr.id:
                    parent_filter = FilterManager.getFilterById(curr.baseId, self.objToTreeId)
                    if parent_filter:
                        b_orphan = False

                if b_orphan:
                    tags.append('orphan')

            if b_circular and curr in circular_path:
                tags.append('circular')

            if len(FilterManager.getFiltersById(curr.id, lookup)) > 1:
                tags.append('duplicate')

            parent = '' if parent_filter is None else self.objToTreeId[parent_filter]
            iid = self.tree.insert(parent, index, '', text=curr.title, tags=tags)
            self.objToTreeId[curr] = iid
            self.treeIdToObj[iid] = curr
            parent_filter = curr

    def fillTree(self, filters=None):
        self.tree.delete(*self.tree.get_children())
        self.objToTreeId.clear()
        self.treeIdToObj.clear()

        if filters is None:
            filters = list(self.fm.getRawFilters())

        for fltr in filters:
            self.addFilterToTree(fltr, filters)

    def tree_selected(self, event=None):
        selected = self.tree.selection()

        if self.reload_needed:
            self._update_categories()
            self._update_ids()
            self.fillTree()
            self.reload_needed = False
            selected = None

        if not selected:
            self.currFilter = None
            self.selected = None
            self.filter_form.form_reset()
            self.setFormState(DISABLED)
        elif self.selected == selected[0]:
            return
        else:
            self.selected = selected[0]
            self.currFilter = self.treeIdToObj[self.selected]

            self.setFormState(NORMAL)
            self.filter_form.form_update(self.currFilter.toDict())

            if self.currFilter in self.fm.autoFilters or self.tree.tag_has('readonly', self.selected):
                self.setFormState(DISABLED)

        self.validateForm()

        if self.currFilter and self.currFilter in self.fm.userFilters:
            self._validate_baseid_not_circular(self.currFilter, list(self.fm.getRawFilters()))

    def createFilterGeneral(self):
        parent = self.lfrm_filter

        self.addColumn(Label(parent, text="Title:"), sticky='e')
        frm = Frame(parent, style='Borderless.TFrame')
        self.addColumn(frm, sticky='wns')

        entry = PlaceholderEntry(frm, ph_text='Enter title..', style='Default.TEntry', width=40)
        self.addColumn(entry, padx=0, pady=0)
        self.filter_form.field_register('title', entry, str)
        self.entry_title = entry

        self.lbl_title_error = Label(frm)
        self.addColumn(self.lbl_title_error, pady=0)
        entry.bind('<FocusOut>', lambda event: self._validate_title_field(), add="+")

        self.addRow(Label(parent, text="ID:"), sticky='e')
        frm = Frame(parent, style='Borderless.TFrame')
        self.addColumn(frm, sticky='wns')

        entry = PlaceholderEntry(frm, 'Enter a unique id..', style='Default.TEntry', width=40)
        self.addColumn(entry, padx=0, pady=0)
        self.filter_form.field_register('id', entry, str)
        self.entry_id = entry

        self.lbl_id_error = Label(frm)
        self.addColumn(self.lbl_id_error, pady=0)
        entry.bind('<FocusOut>', lambda event: self._validate_id_field(), add="+")

        self.addRow(Label(parent, text="Base ID:"), sticky='e')
        frm = Frame(parent, style='Borderless.TFrame')
        self.addColumn(frm, sticky='wns')

        entry = Combobox_Autocomplete(frm, style='Autocomplete.TEntry', width=40,
                                      list_of_items=self.lst_ids, startswith_match=False)
        self.addColumn(entry, padx=0, pady=0)
        self.filter_form.field_register('baseid', entry, str)
        self.entry_baseid = entry

        self.lbl_baseid_error = Label(frm)
        self.addColumn(self.lbl_baseid_error, pady=0)

        entry.bind('<<TrueFocusOut>>', lambda event: self._validate_baseid_field())

        self.addRow(Label(parent, text="Category:"), sticky='e')
        entry = Combobox_Autocomplete(parent, style='Autocomplete.TEntry', width=40,
                                      list_of_items=self.lst_categories, startswith_match=False)
        self.addColumn(entry, sticky='wns')
        self.filter_form.field_register('category', entry, str)

        self.addRow(Label(parent, text="Description:"), sticky='e')
        entry = PlaceholderEntry(parent, 'Enter a description..', style='Default.TEntry', width=80)
        self.addColumn(entry, sticky='wns')
        self.filter_form.field_register('description', entry, str)

        var = BooleanVar()
        entry = Checkbutton(parent, text='Enabled', variable=var)
        entry.var = var
        self.addRow(Frame(parent))
        self.addColumn(entry)
        self.filter_form.field_register('enabled', entry, bool)

    def createFilterCriteria(self):
        parent = self.lfrm_crit
        level = 'criteria'
        self.filter_form.level_register(level)
        is_number_cmd = self.register(_is_number_or_empty)

        ## Name
        self.addColumn(Label(parent, text="Name(s):"), sticky='e')
        entry = PlaceholderEntry(parent, 'Enter names (separated by ,)..', style='Default.TEntry')
        self.addColumn(entry, columnspan=5)
        self.filter_form.field_register('name', entry, list, level)

        ## Type
        self.addRow(Label(parent, text="Type(s):"), sticky='e')
        entry = MultiCombobox(parent, ItemTypeOptions)
        self.addColumn(entry, columnspan=3)
        self.filter_form.field_register('type', entry, type(None), level)

        ## Base
        self.addColumn(Label(parent, text="Base:"), sticky='e')
        entry = PlaceholderEntry(parent, 'Enter item base..', style='Default.TEntry')
        self.addColumn(entry, sticky='ew')
        self.filter_form.field_register('base', entry, str, level)

        ## Price / Buyout
        self.addRow(Label(parent, text="Price:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent)
        self.filter_form.field_register('price_min', entry_min, str, level)
        self.filter_form.field_register('price_max', entry_max, str, level)
        self.entry_price_min = entry_min
        self.entry_price_max = entry_max

        self.entry_price_min.bind('<FocusOut>', lambda event: self._validate_price_field(self.entry_price_min), add="+")
        self.entry_price_max.bind('<FocusOut>', lambda event: self._validate_price_field(self.entry_price_max), add="+")

        self.addColumn(Label(parent, text="Buyout:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('buyout', entry, BoolOption, level)

        self.addRow(Separator(parent), columnspan=8)

        ## DPS
        self.addRow(Label(parent, text="DPS:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('dps_min', entry_min, float, level)
        self.filter_form.field_register('dps_max', entry_max, float, level)

        self.addColumn(Label(parent, text="PDPS:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('pdps_min', entry_min, float, level)
        self.filter_form.field_register('pdps_max', entry_max, float, level)

        self.addColumn(Label(parent, text="EDPS:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('edps_min', entry_min, float, level)
        self.filter_form.field_register('edps_max', entry_max, float, level)

        ## Defense
        self.addRow(Label(parent, text="Armour:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('armour_min', entry_min, float, level)
        self.filter_form.field_register('armour_max', entry_max, float, level)

        self.addColumn(Label(parent, text="Evasion:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('evasion_min', entry_min, float, level)
        self.filter_form.field_register('evasion_max', entry_max, float, level)

        self.addColumn(Label(parent, text="Energy shield:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('es_min', entry_min, float, level)
        self.filter_form.field_register('es_max', entry_max, float, level)

        self.addRow(Separator(parent), columnspan=8)

        ## Sockets
        self.addRow(Label(parent, text="Sockets:"), sticky='e')

        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('sockets_min', entry_min, float, level)
        self.filter_form.field_register('sockets_max', entry_max, float, level)

        self.addColumn(Label(parent, text="Links:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('links_min', entry_min, float, level)
        self.filter_form.field_register('links_max', entry_max, float, level)

        ### Item Level
        self.addColumn(Label(parent, text="Item level:"), sticky='e')

        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('ilvl_min', entry_min, float, level)
        self.filter_form.field_register('ilvl_max', entry_max, float, level)

        ## Quality / Level / Exp

        ### Quality
        self.addRow(Label(parent, text="Quality:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('quality_min', entry_min, float, level)
        self.filter_form.field_register('quality_max', entry_max, float, level)

        ### Level
        self.addColumn(Label(parent, text="Level:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('level_min', entry_min, float, level)
        self.filter_form.field_register('level_max', entry_max, float, level)

        ### Experience
        is_valid_exp_cmd = self.register(functools.partial(_is_number_or_empty, min=0, max=100))
        self.addColumn(Label(parent, text="Experience(%):"), sticky='e')
        entry = Spinbox(parent, from_=0, to=100, increment=1, format='%1.f', width=5,
                        validate='all', validatecommand=(is_valid_exp_cmd, '%P'))
        self.addColumn(entry, sticky='wns')
        self.filter_form.field_register('exp', entry, float, level)

        self.addRow(Label(parent, text="Corrupted:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('corrupted', entry, BoolOption, level)

        self.addColumn(Label(parent, text="Mod count:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('modcount_min', entry_min, float, level)
        self.filter_form.field_register('modcount_max', entry_max, float, level)

        self.addColumn(Label(parent, text="Stack size:"), sticky='e')
        entry_min, entry_max = self._add_min_max(parent, validate='all', validatecommand=(is_number_cmd, '%P'))
        self.filter_form.field_register('stacksize_min', entry_min, float, level)
        self.filter_form.field_register('stacksize_max', entry_max, float, level)

        ## Comboboxes Crafted / Identified / Modifiable
        self.addRow(Label(parent, text="Modifiable:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('modifiable', entry, BoolOption, level)

        self.addColumn(Label(parent, text="Identified:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('identified', entry, BoolOption, level)

        self.addColumn(Label(parent, text="Crafted:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('crafted', entry, BoolOption, level)

        self.addColumn(Label(parent, text="Enchanted:"), sticky='e')
        entry = Combobox(parent, values=boolOptions, state=READONLY)
        self.addColumn(entry)
        self.filter_form.field_register('enchanted', entry, BoolOption, level)

        # self.addRow(Separator(parent), columnspan=8)
        frm = LabelFrame(parent, text='Filter Groups', style='Borderless.TLabelframe')
        self.addRow(frm, columnspan=8, padx=0, pady=5)
        parent.rowconfigure(frm.grid_info()['row'], weight=1)
        # frm.rowconfigure(0, weight=1, minsize=150)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        self.frm_fgs_container = Scrolling_Area(frm)
        self.frm_fgs_container.innerframe.columnconfigure(0, weight=1)

        self.addRow(self.frm_fgs_container, padx=0, pady=0)

        self.frm_fgs = Frame(self.frm_fgs_container.innerframe, style='Borderless.TFrame')
        # self.frm_fgs = ScrolledWindow(self.frm_fgs_container)
        self.addRow(Frame(self.frm_fgs, style='Borderless.TFrame', width=1, height=1), padx=0, pady=0)
        self.addRow(self.frm_fgs, padx=0, pady=0)
        self.frm_fgs.columnconfigure(0, weight=1)
        self.filter_form.field_register('fgs', self.frm_fgs, type(None), level,
                                        get_func=self.getFilterGroups, set_func=self.setFilterGroups,
                                        set_state_func=self.setFilterGroupsState)

        self.btn_createfg = Button(self.frm_fgs_container.innerframe, text='Add Filter Group', command=self.addFilterGroup)
        self.addRow(self.btn_createfg, sticky='e')

    def _is_id_field_valid(self):
        val = self.entry_id.get_value().lower()

        if self.currFilter:
            if self.currFilter not in self.fm.autoFilters and val.startswith('_'):
                return False, 'Underscore prefix is reserved for generated filters'

            lookup = list(self.objToTreeId)
            lookup.remove(self.currFilter)

            duplicates = FilterManager.getFiltersById(val, lookup)
            if duplicates:
                return False, 'ID must be unique. Duplicate of: {}'.format([flt.title for flt in duplicates])

        # elif self.currFilter and self.currFilter.id.lower() != val and val in self.lst_ids:
        #     return False, 'Filter id must be unique'

        return True, ''

    def _validate_id_field(self):
        valid, reason = self._is_id_field_valid()

        if valid:
            self.entry_id.hideTooltip()
            return True
        else:
            self.entry_id.showTooltip(reason)
            return False

    def _is_baseid_field_valid(self):
        val = self.entry_baseid.get_value().lower()

        if val == '' or val in self.lst_ids:
            return True, ''
        else:
            return False, 'Base ID not found'

    def _validate_baseid_field(self):
        valid, reason = self._is_baseid_field_valid()

        if valid:
            self.entry_baseid.hideTooltip()
            return True
        else:
            self.entry_baseid.showTooltip(reason)
            return False

    def _is_title_field_valid(self):
        val = self.entry_title.get_value()

        if self.currFilter and self.currFilter not in self.fm.autoFilters and not val:
            return False, 'Title is a required field'
        return True, ''

    def _validate_title_field(self):
        valid, reason = self._is_title_field_valid()
        if valid:
            self.entry_title.hideTooltip()
            # self.lbl_title_error.config(text='')
            return True
        else:
            self.entry_title.showTooltip(reason)
            return False

    def _is_price_valid(self, val):
        if val.strip() == '':
            return True, ''
        if not cm.isOverridePriceValid(val):
            return False, 'Price format is: <amount> <currency>\nExamples: 100 chaos, 20 ex, 5 divine\n' \
                          'Prices can also be relative to their base.\n' \
                          'Examples: / 3, * 0.5, +2.5 ex, -20 chaos'
        return True, ''

    def _validate_price_field(self, widget):
        valid, reason = self._is_price_valid(widget.get())
        if valid:
            widget.hideTooltip()
            return True
        else:
            widget.showTooltip(reason, pos=TIP_BELOW)
            return False

    def validateForm(self):
        """ This function provides validation for all fields with tooltips.
        When there are multiple errors, the user will be lead from one error to the next until all are resolved. """

        self.entry_title.hideTooltip()
        self.entry_id.hideTooltip()
        self.entry_baseid.hideTooltip()
        self.entry_price_min.hideTooltip()
        self.entry_price_max.hideTooltip()

        for child in list(self.frm_fgs.children.values()):
            if isinstance(child, FilterGroupWidget):
                for mfw in child.mfws:
                    mfw.entry_mod.hideTooltip()

        if not self._validate_title_field():
            self.entry_title.focus_set()
            return False
        if not self._validate_id_field():
            self.entry_id.focus_set()
            return False
        if not self._validate_baseid_field():
            self.entry_baseid.focus_set()
            return False
        if not self._validate_price_field(self.entry_price_min):
            self.entry_price_min.focus_set()
            return False
        if not self._validate_price_field(self.entry_price_max):
            self.entry_price_max.focus_set()
            return False

        for child in list(self.frm_fgs.children.values()):
            if isinstance(child, FilterGroupWidget):
                for mfw in child.mfws:
                    if not mfw.validateMod():
                        mfw.entry_mod.focus_set()
                        return False

        return True

    def _add_min_max(self, parent, **kw):
        frm = Frame(parent, style='Borderless.TFrame')
        self.addColumn(frm)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.grid_propagate(0)

        entry_min = TooltipEntry(frm, style='Default.TEntry', **kw)
        self.addColumn(entry_min, padx=0, pady=0, sticky='nsew')

        entry_max = TooltipEntry(frm, style='Default.TEntry', **kw)
        self.addColumn(entry_max, padx=0, pady=0, sticky='nsew')

        return entry_min, entry_max

    def addColumn(self, widget, **kw):
        row, col = self.positions.get(widget.winfo_parent(), (0, 0))
        span = kw.get('columnspan', 1)
        padx = kw.get('padx', 5)
        pady = kw.get('pady', 3)
        sticky = kw.get('sticky', 'nsew')
        widget.grid(kw, row=row, column=col, padx=padx, sticky=sticky, pady=pady)
        col = col + span
        self.positions[widget.winfo_parent()] = row, col

    def addRow(self, widget, **kw):
        row, col = self.positions.get(widget.winfo_parent(), (-1, 0))
        col = 0
        row = row + 1
        self.positions[widget.winfo_parent()] = row, col
        self.addColumn(widget, **kw)

    def addFilterGroup(self, fg=None):
        fgw = FilterGroupWidget(self.frm_fgs, fg)
        self.addRow(fgw, padx=0, pady=0)

    def onClose(self):
        self.destroy()

    def getFilterGroups(self, container):
        fgs = []
        for child in list(container.children.values()):
            if isinstance(child, FilterGroupWidget):
                fg = child.toFilterGroup()
                if len(fg.mfs):
                    fgs.append(fg.toDict())
        return fgs if fgs else None

    def setFilterGroups(self, container, fgs_data=None):
        for child in list(container.children.values()):
            if isinstance(child, FilterGroupWidget):
                child.destroy()

        fgs = []
        if fgs_data:
            for fg_data in fgs_data:
                try:
                    fg_type = FilterGroupType(fg_data['type'])
                except ValueError:
                    # TODO: inform user filter fg had a bad type?
                    fg_type = FilterGroupType.All

                fg = FilterGroupFactory.create(fg_type, fg_data)
                if len(fg.mfs):
                    fgs.append(fg)

        for fg in fgs:
            self.addFilterGroup(fg)

        if not fgs:
            self.addFilterGroup()

    def setFilterGroupsState(self, container, state):
        for child in list(container.children.values()):
            if isinstance(child, FilterGroupWidget):
                child.set_state(state)

    def setFormState(self, state):
        self.filter_form.form_set_state(state)
        self.btn_createfg.config(state=state)
        self.updateButtonState()

    def updateButtonState(self):
        if self.currFilter:
            if self.currFilter in self.fm.autoFilters or (self.selected and self.tree.tag_has('readonly', self.selected)):
                if self.compiling.get():
                    self.btn_copy.config(state=DISABLED)
                else:
                    self.btn_copy.config(state=NORMAL)
                self.btn_delete.config(state=DISABLED)
                self.btn_save.config(state=DISABLED)
                self.btn_discard.config(state=DISABLED)
                self.btn_reset.config(state=DISABLED)
            elif self.compiling.get():
                self.btn_copy.config(state=DISABLED)
                self.btn_delete.config(state=DISABLED)
                self.btn_save.config(state=DISABLED)
                self.btn_discard.config(state=NORMAL)
                self.btn_reset.config(state=NORMAL)
            else:
                self.btn_copy.config(state=NORMAL)
                self.btn_delete.config(state=NORMAL)
                self.btn_save.config(state=NORMAL)
                self.btn_discard.config(state=NORMAL)
                self.btn_reset.config(state=NORMAL)
        else:
            self.btn_copy.config(state=DISABLED)
            self.btn_delete.config(state=DISABLED)
            self.btn_save.config(state=DISABLED)
            self.btn_discard.config(state=DISABLED)
            self.btn_reset.config(state=DISABLED)

        if self.compiling.get():
            self.btn_new.config(state=DISABLED)
        else:
            self.btn_new.config(state=NORMAL)

    def _onCompilingChange(self):
        self.updateButtonState()
        self.update_idletasks()

    # def filterTreeview(self, text):
    #
    #     self._detachTreeItems()
    #
    #     # if text == '':
    #     #     matches = self.tree.get_children()
    #     # else:
    #     matches = self._search_tree(text)
    #
    #     if 'crystal' in text:
    #         for match in matches:
    #             print(self.treeIdToObj[match].title)
    #
    #     for match in matches:
    #         iid = match
    #
    #         while True:
    #             parent = self.tree.parent(iid)
    #             if not parent:
    #                 break
    #             iid = parent
    #
    #         self.tree.reattach(iid, '', END)
    #
    #     if self.currFilter and self.objToTreeId[self.currFilter] in matches:
    #         self.tree.see(self.objToTreeId[self.currFilter])

    # def _detachTreeItems(self, root=''):
    #     for child in self.tree.get_children(root):
    #         self._detachTreeItems(child)
    #
    #     if root:
    #         self.tree.detach(root)

    # def _search_match(self, escaped_entry_data, item):
    #     if re.search(escaped_entry_data, item, re.IGNORECASE):
    #         return True
    #     else:
    #         return False

    # def _search_tree(self, text):
    #     if not text:
    #         return self.treeIdToObj
    #
    #     escaped_text = re.escape(text)
    #     res = []
    #     for fltr in self.objToTreeId:
    #         if re.search(escaped_text, fltr.title, re.IGNORECASE):
    #             res.append(self.objToTreeId[fltr])
    #     return res


class FormHelper:
    class Field:
        def __init__(self, widget, val_type, get_func, set_func, set_state_func, default):
            self.widget = widget
            self.type = val_type
            self.get_func = get_func
            self.set_func = set_func
            self.set_state_func = set_state_func
            self.default = default

    class Level(collections.OrderedDict):
        pass

    def __init__(self):
        self.form_fields = collections.OrderedDict()

    def field_register(self, key, widget, val_type, level=None, get_func=None, set_func=None, set_state_func=None, default=None):
        field = FormHelper.Field(widget, val_type, get_func, set_func, set_state_func, default)

        if level is None:
            self.form_fields[key] = field
        else:
            self.form_fields[level][key] = field

    def level_register(self, name):
        self.form_fields[name] = FormHelper.Level()

    def form_serialize(self, root=None):
        data = collections.OrderedDict()

        if root is None:
            root = self.form_fields

        for key in root:
            entry = root[key]
            if isinstance(entry, FormHelper.Level):
                data[key] = self.form_serialize(root[key])
            else:
                val = self.get_entry_value(entry)

                if val == '' or val is None:
                    continue

                try:
                    if entry.type in (int, float, bool):
                        typed_val = entry.type(val)
                    elif entry.type is list:
                        typed_val = [st.strip() for st in val.split(sep=',')]
                    elif issubclass(entry.type, Enum):
                        # val here would be the name of the enum value
                        typed_val = (entry.type[val]).value
                    elif entry.type is str:
                        typed_val = str(val)
                    else:
                        typed_val = val

                    if typed_val is not None:
                        data[key] = typed_val
                except ValueError:
                    print('serilization failed for {}: {}'.format(key, val))

        return data

    def form_update(self, data, root=None):
        if root is None:
            root = self.form_fields

        for key in root:
            entry = root[key]
            if isinstance(entry, FormHelper.Field):
                self.reset_entry_value(entry)

        for key in data:
            if key not in root:
                continue

            entry = root[key]
            val = data[key]

            if isinstance(entry, FormHelper.Level):
                self.form_update(val, entry)
            else:
                try:
                    # if entry.type in (int, float, bool, str):
                    #     pass
                    if entry.type is float and val == int(val):
                        val = int(val)
                    if entry.type is list:
                        field_val = self._list_to_field(val)
                    elif issubclass(entry.type, Enum):
                        field_val = (entry.type(val)).name
                    else:
                        field_val = val

                    self.set_entry_value(entry, field_val)
                except ValueError:
                    print('conversion failed for {}: {}'.format(key, val))

    def form_set_state(self, state=DISABLED, root=None):
        if root is None:
            root = self.form_fields

        for key in root:
            entry = root[key]
            if isinstance(entry, FormHelper.Field):
                self.set_entry_state(entry, state)
            elif isinstance(entry, FormHelper.Level):
                self.form_set_state(state, entry)

    def form_reset(self, root=None):
        if root is None:
            root = self.form_fields

        for key in root:
            entry = root[key]
            if isinstance(entry, FormHelper.Field):
                self.reset_entry_value(entry)
            elif isinstance(entry, FormHelper.Level):
                self.form_reset(entry)

    def get_entry_value(self, entry):
        w = entry.widget
        if entry.get_func:
            return entry.get_func(w)
        if isinstance(w, PlaceholderEntry):
            return w.get_value().strip()
        elif isinstance(w, MultiCombobox):
            return w.get_value()
        elif isinstance(w, Combobox):
            return w.get()
        elif isinstance(w, Combobox_Autocomplete):
            return w.get_value().strip()
        elif isinstance(w, Spinbox):
            return w.get().strip()
        elif isinstance(w, Entry):
            return w.get().strip()
        elif isinstance(w, Checkbutton):
            return w.var.get()

    # more like insert since it relies on reset
    def set_entry_value(self, entry, val):
        w = entry.widget
        if entry.set_func:
            entry.set_func(w, val)
        elif isinstance(w, PlaceholderEntry):
            w.set_value(val)
        elif isinstance(w, MultiCombobox):
            w.set_value(val)
        elif isinstance(w, Combobox):
            w.set(val)
        elif isinstance(w, Combobox_Autocomplete):
            w.set_value(val, True)
            # w.insert(END, val)
        elif isinstance(w, Spinbox):
            w.set(val)
        elif isinstance(w, Entry):
            w.insert(END, val)
        elif isinstance(w, Checkbutton):
            w.var.set(val)

    def reset_entry_value(self, entry):
        w = entry.widget
        if entry.set_func:
            entry.set_func(w, entry.default)
        elif isinstance(w, PlaceholderEntry):
            w.Reset()
        elif isinstance(w, MultiCombobox):
            w.set_value()
        elif isinstance(w, Combobox):
            w.current(0)
        elif isinstance(w, Combobox_Autocomplete):
            # w.delete(0, END)
            w.set_value('', True)
        elif isinstance(w, Spinbox):
            w.delete(0, END)
            # w.set(0)
        elif isinstance(w, Entry):
            w.delete(0, END)
        elif isinstance(w, Checkbutton):
            w.var.set(1)

    def _list_to_field(self, lst):
        s = None
        for item in lst:
            if not s:
                s = str(item)
            else:
                s += ', ' + str(item)
        return s

    def set_entry_state(self, entry, state):
        w = entry.widget
        if entry.set_state_func:
            entry.set_state_func(w, state)
        elif isinstance(w, PlaceholderEntry):
            w.set_state(state)
        elif isinstance(w, MultiCombobox):
            w.config(state=state)
        elif isinstance(w, Combobox):
            if state == NORMAL:
                w.config(state=READONLY)
            else:
                w.config(state=DISABLED)
        elif isinstance(w, Combobox_Autocomplete):
            w.config(state=state)
        elif isinstance(w, Spinbox):
            w.config(state=state)
        elif isinstance(w, Entry):
            w.config(state=state)
        elif isinstance(w, Checkbutton):
            w.config(state=state)


def _is_number_or_empty(text, min=None, max=None):
    try:
        # text = text.strip()
        if text == '':
            return True

        if text.find(' ') != -1:
            return False

        num = float(text)
        if min is not None and num < min:
            return False
        if max is not None and num > max:
            return False
        return True
    except ValueError:
        return False

