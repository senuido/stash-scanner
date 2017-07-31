# Based on: http://code.activestate.com/recipes/580770-combobox-autocomplete/ by Miguel Martinez Lopez
# Modified to work with toplevel windows and some other adjustments

from tkinter import *
from tkinter.ttk import *

from ui.TooltipEntry import TooltipEntry


def autoscroll(sbar, first, last):
    """Hide and show scrollbar as needed."""
    first, last = float(first), float(last)
    if first <= 0 and last >= 1:
        sbar.grid_remove()
    else:
        sbar.grid()
    sbar.set(first, last)


class Combobox_Autocomplete(TooltipEntry, object):

    def __init__(self, master, list_of_items=None, autocomplete_function=None, listbox_width=None, listbox_height=7,
                 ignorecase_match=True, startswith_match=True, vscrollbar=True, hscrollbar=True, *args, **kwargs):
        if hasattr(self, "autocomplete_function"):
            if autocomplete_function is not None:
                raise ValueError("Combobox_Autocomplete subclass has 'autocomplete_function' implemented")
        else:
            if autocomplete_function is not None:
                self.autocomplete_function = autocomplete_function
            else:
                if list_of_items is None:
                    raise ValueError("If not guiven complete function, list_of_items can't be 'None'")

                if not ignorecase_match:
                    if startswith_match:
                        def matches_function(entry_data, item):
                            return item.startswith(entry_data)
                    else:
                        def matches_function(entry_data, item):
                            return item in entry_data

                    self.autocomplete_function = lambda entry_data: [item for item in self.list_of_items if
                                                                     matches_function(entry_data, item)]
                else:
                    if startswith_match:
                        def matches_function(escaped_entry_data, item):
                            if re.match(escaped_entry_data, item, re.IGNORECASE):
                                return True
                            else:
                                return False
                    else:
                        def matches_function(escaped_entry_data, item):
                            if re.search(escaped_entry_data, item, re.IGNORECASE):
                                return True
                            else:
                                return False

                    def autocomplete_function(entry_data):
                        escaped_entry_data = re.escape(entry_data)
                        return [item for item in self.list_of_items if matches_function(escaped_entry_data, item)]

                    self.autocomplete_function = autocomplete_function

        self._listbox_height = int(listbox_height)
        self._listbox_width = listbox_width

        self.list_of_items = list_of_items

        self._use_vscrollbar = vscrollbar
        self._use_hscrollbar = hscrollbar

        # kwargs.setdefault("background", "white")

        if "textvariable" in kwargs:
            self._entry_var = kwargs["textvariable"]
        else:
            self._entry_var = kwargs["textvariable"] = StringVar()

        # TooltipEntry.__init__(self, master, **kwargs)
        super().__init__(master, *args, **kwargs)

        self._trace_id = self._entry_var.trace('w', self._on_change_entry_var)

        self._listbox = None

        self.bind("<Control-space>",lambda event: self.post_listbox())
        self.bind("<Up>", self._previous)
        self.bind("<Down>", self._next)
        self.bind('<Control-n>', self._next)
        self.bind('<Control-p>', self._previous)

        self.bind("<Return>", self._update_entry_from_listbox)
        self.bind("<Escape>", lambda event: self.unpost_listbox())
        # self.bind("<FocusOut>", lambda event: self._update_entry_from_listbox(event, False))
        # self.bind("<FocusOut>", lambda event: self.after(50, self._on_focus_out, event))
        self.bind("<FocusOut>", self._on_focus_out)
        parent = self.master
        while not isinstance(parent, (Toplevel, Tk)):
            parent = parent.master

        self.parent_window = parent

    def _on_focus_out(self, event):
        if self._listbox and self._listbox.winfo_name() in str(self._listbox.focus_get()):
            return
        self.unpost_listbox()
        self.event_generate('<<TrueFocusOut>>')

    def _on_change_entry_var(self, name, index, mode):

        entry_data = self._entry_var.get()

        if entry_data == '':
            self.unpost_listbox()
            # self.focus()
        else:
            values = self.autocomplete_function(entry_data)
            if values:
                if self._listbox is None:
                    self._build_listbox(values)
                else:
                    self._listbox.delete(0, END)

                    height = min(self._listbox_height, len(values))
                    self._listbox.configure(height=height)

                    for item in values:
                        self._listbox.insert(END, item)

            else:
                self.unpost_listbox()
                self.focus()

    def _build_listbox(self, values):
        listbox_frame = Frame(self.parent_window, padding=0)

        if self._listbox_width:
            width = self._listbox_width
        else:
            width = self.winfo_width()

        self._listbox = Listbox(listbox_frame, background="white", selectmode=SINGLE, activestyle="none",
                                exportselection=False)
        self._listbox.grid(row=0, column=0, sticky='nsew', padx=0, pady=0)

        self._listbox.bind("<ButtonRelease-1>", self._update_entry_from_listbox)
        self._listbox.bind("<Return>", self._update_entry_from_listbox)
        self._listbox.bind("<Escape>", lambda event: self.unpost_listbox())
        # self._listbox.bind("<FocusOut>", lambda event: self.after(50, self._on_focus_out_list, event))
        self._listbox.bind('<Control-n>', self._next)
        self._listbox.bind('<Control-p>', self._previous)

        if self._use_vscrollbar:
            vbar = Scrollbar(listbox_frame, orient=VERTICAL, command=self._listbox.yview)
            vbar.grid(row=0, column=1, sticky='ns')

            self._listbox.configure(yscrollcommand=lambda f, l: autoscroll(vbar, f, l))

        if self._use_hscrollbar:
            hbar = Scrollbar(listbox_frame, orient=HORIZONTAL, command=self._listbox.xview)
            hbar.grid(row=1, column=0, sticky='ew')

            self._listbox.configure(xscrollcommand=lambda f, l: autoscroll(hbar, f, l))

        listbox_frame.grid_columnconfigure(0, weight=1)
        listbox_frame.grid_rowconfigure(0, weight=1)

        listbox_frame.place(in_=self, x=0, y=self.winfo_height(), width=width)

        height = min(self._listbox_height, len(values))
        self._listbox.configure(height=height)

        for item in values:
            self._listbox.insert(END, item)

    def post_listbox(self):
        if self._listbox is not None: return

        entry_data = self._entry_var.get()
        if entry_data == '': return

        values = self.autocomplete_function(entry_data)
        if values:
            self._build_listbox(values)

    def unpost_listbox(self):
        if self._listbox is not None:
            self._listbox.master.destroy()
            self._listbox = None

    def get_value(self):
        return self._entry_var.get()

    def set_value(self, text, close_dialog=False):
        self._set_var(text)

        if close_dialog:
            self.unpost_listbox()

        self.icursor(END)
        self.xview_moveto(1.0)

    def _set_var(self, text):
        self._entry_var.trace_vdelete("w", self._trace_id)
        self._entry_var.set(text)
        self._trace_id = self._entry_var.trace('w', self._on_change_entry_var)

    def _update_entry_from_listbox(self, event, focus=True):
        if self._listbox is not None:
            current_selection = self._listbox.curselection()

            if current_selection:
                text = self._listbox.get(current_selection)
                self._set_var(text)

            self._listbox.master.destroy()
            self._listbox = None

            if focus:
                self.focus()
                self.icursor(END)
                self.xview_moveto(1.0)

        return "break"

    def _previous(self, event):
        if self._listbox is not None:
            current_selection = self._listbox.curselection()

            if len(current_selection) == 0:
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            else:
                index = int(current_selection[0])
                self._listbox.selection_clear(index)

                if index == 0:
                    index = END
                else:
                    index -= 1

                self._listbox.see(index)
                self._listbox.selection_set(first=index)
                self._listbox.activate(index)

        return "break"

    def _next(self, event):
        if self._listbox is not None:

            current_selection = self._listbox.curselection()
            if len(current_selection) == 0:
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            else:
                index = int(current_selection[0])
                self._listbox.selection_clear(index)

                if index == self._listbox.size() - 1:
                    index = 0
                else:
                    index += 1

                self._listbox.see(index)
                self._listbox.selection_set(index)
                self._listbox.activate(index)
        return "break"


if __name__ == '__main__':
    list_of_items = ["Cordell Cannata", "Lacey Naples", "Zachery Manigault", "Regan Brunt", "Mario Hilgefort",
                     "Austin Phong", "Moises Saum", "Willy Neill", "Rosendo Sokoloff", "Salley Christenberry",
                     "Toby Schneller", "Angel Buchwald", "Nestor Criger", "Arie Jozwiak", "Nita Montelongo",
                     "Clemencia Okane", "Alison Scaggs", "Von Petrella", "Glennie Gurley", "Jamar Callender",
                     "Titus Wenrich", "Chadwick Liedtke", "Sharlene Yochum", "Leonida Mutchler", "Duane Pickett",
                     "Morton Brackins", "Ervin Trundy", "Antony Orwig", "Audrea Yutzy", "Michal Hepp",
                     "Annelle Hoadley", "Hank Wyman", "Mika Fernandez", "Elisa Legendre", "Sade Nicolson", "Jessie Yi",
                     "Forrest Mooneyhan", "Alvin Widell", "Lizette Ruppe", "Marguerita Pilarski", "Merna Argento",
                     "Jess Daquila", "Breann Bevans", "Melvin Guidry", "Jacelyn Vanleer", "Jerome Riendeau",
                     "Iraida Nyquist", "Micah Glantz", "Dorene Waldrip", "Fidel Garey", "Vertie Deady",
                     "Rosalinda Odegaard", "Chong Hayner", "Candida Palazzolo", "Bennie Faison", "Nova Bunkley",
                     "Francis Buckwalter", "Georgianne Espinal", "Karleen Dockins", "Hertha Lucus", "Ike Alberty",
                     "Deangelo Revelle", "Juli Gallup", "Wendie Eisner", "Khalilah Travers", "Rex Outman",
                     "Anabel King", "Lorelei Tardiff", "Pablo Berkey", "Mariel Tutino", "Leigh Marciano", "Ok Nadeau",
                     "Zachary Antrim", "Chun Matthew", "Golden Keniston", "Anthony Johson", "Rossana Ahlstrom",
                     "Amado Schluter", "Delila Lovelady", "Josef Belle", "Leif Negrete", "Alec Doss", "Darryl Stryker",
                     "Michael Cagley", "Sabina Alejo", "Delana Mewborn", "Aurelio Crouch", "Ashlie Shulman",
                     "Danielle Conlan", "Randal Donnell", "Rheba Anzalone", "Lilian Truax", "Weston Quarterman",
                     "Britt Brunt", "Leonie Corbett", "Monika Gamet", "Ingeborg Bello", "Angelique Zhang",
                     "Santiago Thibeau", "Eliseo Helmuth"]

    root = Tk()
    root.geometry("300x200")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frm_form = Frame(root)
    frm_form.grid(row=0, column=0)
    lbl_names = Label(frm_form, text='Name:')
    lbl_names.grid(row=0, column=0, padx=5, pady=5)
    entry_name = Combobox_Autocomplete(frm_form, list_of_items=list_of_items, startswith_match=False)
    entry_name.grid(row=0, column=1, padx=5)

    entry_name.focus()

    lbl_names = Label(frm_form, text='Food:')
    lbl_names.grid(row=1, column=0, padx=5, pady=5)
    entry_food = Combobox_Autocomplete(frm_form, list_of_items=['Apples', 'Oranges', 'Avocados'], startswith_match=False)
    entry_food.grid(row=1, column=1, padx=5)

    root.mainloop()