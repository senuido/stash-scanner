from tkinter.ttk import Treeview, Entry, Combobox
from tkinter.constants import *
import re

from ui.TooltipEntry import TooltipEntry, TIP_BELOW

class MyTreeview(Treeview):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)

    def tag_add(self, tagname, items):
        self.tk.call(self._w, 'tag', 'add', tagname, items)

    def tag_remove(self, tagname, items):
        self.tk.call(self._w, 'tag', 'remove', tagname, items)

    def tag_names(self):
        return self.tk.splitlist(self.tk.call(self._w, 'tag', 'names'))

    def search(self, search_text, find_next=False):
        if not search_text:
            return

        selected = self.selection()
        if not selected:
            children = self.get_children()
            if not children:
                return  # empty tree
            start_iid = children[0]
        else:
            start_iid = selected[0]

        search_text = re.escape(search_text)

        if find_next:
            start_iid = self._get_next(start_iid)

        # print('start ID: ', start_iid)
        curr_iid = start_iid

        while True:
            text = self.item(curr_iid, 'text')
            # print(text)
            if re.search(search_text, text, re.IGNORECASE):
                self.selection_set(curr_iid)
                self.see(curr_iid)
                break

            curr_iid = self._get_next(curr_iid)

            if curr_iid == start_iid:
                break

    def _get_next(self, curr_iid):
        children = self.get_children(curr_iid)
        if children:
            next_iid = children[0]
        else:
            while True:
                next_iid = self.next(curr_iid)
                if not next_iid:  # last child -> get the next of parent
                    curr_iid = self.parent(curr_iid)
                    if not curr_iid:  # last item in tree -> get the first item
                        # reached_end = True
                        next_iid = self.get_children()[0]
                if next_iid:
                    break

        return next_iid

    def clear(self):
        self.delete(*self.get_children())

class EditableTreeview(MyTreeview):

    class ColEntry:
        def __init__(self, entry, accept_events=('<Return>', ), func_validate=None):
            self.entry = entry
            self.accept_events = accept_events
            self.func_validate = func_validate

        def hide(self):
            self.entry.place_forget()
            if isinstance(self.entry, TooltipEntry):
                self.entry.hideTooltip()

        def show(self, x, y, width, height):
            self.entry.place(in_=self.entry.master, x=x, y=y, width=width, height=height)
            self.validate()
            # self.entry.focus()
            # if isinstance(self.entry, TooltipEntry):
            #     self.entry.showTooltip()

        def get(self):
            return self.entry.get()

        def set(self, val):
            if isinstance(self.entry, Combobox):
                self.entry.set(val)
            else:
                self.entry.delete(0, END)
                self.entry.insert(0, val)

        def validate(self):
            if self.func_validate:
                return self.func_validate(self.entry)
            return True

    def __init__(self, master, on_cell_update=None, **kw):
        super().__init__(master, **kw)
        self.bind('<1>', self.on_click)
        self.cent = None
        self.selected_cell = None
        self.col_entries = {}
        self.onCellUpdate = on_cell_update
        self.bind('<Configure>', self.updateEntryPosition, add='+')

        # TODO: fix mousescrolling to apply before edit entry position update
        self.bind('<MouseWheel>', self.on_entry_close, add='+')
        # self.bind('<MouseWheel>', self.updateEntryPosition, add='+')

    def register_column(self, id, col_entry):
        if not isinstance(col_entry, EditableTreeview.ColEntry):
            raise ValueError('col_entry must be a subclass of ColEntry')

        lst = list(self['columns'])
        if id not in lst:
            lst.append(id)
            self['columns'] = lst
            # self.init_column(id)

        self.col_entries[id] = col_entry
        for seq in col_entry.accept_events:
            col_entry.entry.bind(seq, self._on_entry_accept)

        col_entry.entry.bind('<FocusOut>', self._entry_focus_out)
        col_entry.entry.bind('<Escape>', self.on_entry_close)

    # def init_column(self, id):
    #     self.heading(id, text=id, anchor=W, command=lambda col=id: self.sort_by(col, descending=True))

    def sort_col(self, col, reverse=True, key=None, default=None):
        data = []

        for iid in self.get_children(''):
            if col == '#0':
                val = self.item(iid, 'text')
            else:
                val = self.set(iid, col)
            if default is not None and val == '':
                val = default

            if key:
                val = key(val)

            if val is not None:
                data.append((val, iid))

        data.sort(reverse=reverse)

        for idx, item in enumerate(data):
            self.move(item[1], '', idx)

        self.heading(col, command=lambda col=col: self.sort_col(col, not reverse, key, default))


    # def sort_by(self, col, descending):
    #     """
    #     sort tree contents when a column header is clicked
    #     """
    #     # grab values to sort
    #     if col == '#0':
    #         data = [(self.item(child_ID, 'text'), child_ID) for child_ID in self.get_children('')]
    #     else:
    #         data = [(self.set(child_ID, col), child_ID) for child_ID in self.get_children('')]
    #
    #     # if the data to be sorted is numeric change to float
    #     try:
    #         data = [(0 if number == '' else float(number), child_ID) for number, child_ID in data]
    #     except ValueError:
    #         pass
    #
    #     # now sort the data in place
    #     data.sort(reverse=descending)
    #     for idx, item in enumerate(data):
    #         self.move(item[1], '', idx)
    #
    #     # switch the heading so that it will sort in the opposite direction
    #     self.heading(col, command=lambda col=col: self.sort_by(col, not descending))

    def on_click(self, event):
        region = self.identify_region(event.x, event.y)
        iid, col = self.identify_row(event.y), self.identify_column(event.x)
        # print('region: {}, location {}-{}'.format(region, iid, col))
        if region != 'cell':
            self.on_entry_close()
            return

        # if self.selected_cell and self.selected_cell == (iid, col):
        #     return

        # ignore event if accepting previous entry failed
        if not self._on_entry_accept():
            return "break"

        col_id = self.column(col, 'id')
        if col_id not in self.col_entries:
            return

        self.cent = self.col_entries[col_id]
        self.selected_cell = iid, col
        cell_data = self.set(iid, col)

        self.cent.set(cell_data)
        self.cent.show(*self.bbox(iid, col))
        self.selection_set(iid)
        self.cent.entry.focus()
        return 'break'

    def _entry_focus_out(self, event=None):
        if not self.selected_cell:
            return

        entry = self.cent.entry

        new_focus = entry.tk.call('focus')
        if new_focus and entry.winfo_name() not in str(new_focus):
            self._on_entry_accept()

    def _on_entry_accept(self, event=None):
        if not self.selected_cell:
            return True

        iid, col = self.selected_cell

        if self.cent.validate():
            previous = self.set(iid, col)
            new = self.cent.get()
            self.set(iid, col, new)
            # self.event_generate('<<RowUpdated>>')
            if self.onCellUpdate:
                self.onCellUpdate(iid, col, previous, new)
            self.on_entry_close()
            return True

        # self.selection_set(iid)
        return False

    def on_entry_close(self, event=None):
        if not self.selected_cell:
            return

        self.cent.hide()
        self.selected_cell = None
        self.cent = None

    def clear(self):
        self.on_entry_close()
        MyTreeview.clear(self)

    def xview(self, *args):
        super().xview(*args)
        self.updateEntryPosition()

    def yview(self, *args):
        super().yview(*args)
        self.updateEntryPosition()

    def updateEntryPosition(self, event=None):
        #TODO: full scrroll support?
        if self.selected_cell:
            # print('selected cell: ', *self.selected_cell)
            bbox = self.bbox(*self.selected_cell)
            if bbox == "":
                self.cent.hide()
            else:
                self.cent.show(*bbox)
                # self.cent.entry.place(x=x, y=y, width=width, height=height)

            # self.selection_set(self.selected_cell[0])
        # self.on_entry_close()

    # def xview_scroll(self, number, what):
    #     self.on_entry_close()
    #     super().xview_scroll(number, what)
    #
    # def yview_scroll(self, number, what):
    #     self.on_entry_close()
    #     super().yview_scroll(number, what)
    #
    # def xview_moveto(self, fraction):
    #     self.on_entry_close()
    #     super().xview_moveto(fraction)
    #
    # def yview_moveto(self, fraction):
    #     self.on_entry_close()
    #     super().yview_moveto(fraction)


if __name__ == '__main__':
    from tkinter import Tk
    from tkinter.constants import *

    root = Tk()
    tree = EditableTreeview(root)
    tree.pack()

    tree['columns'] = ('Title', 'Item Price', 'Filter Price', 'Filter Force State')

    def validate_price(widget):
        valid = widget.get() == '100 chaos' or widget.get() == ''
        if not valid:
            widget.showTooltip('Invalid price', TIP_BELOW)
            widget.focus()
        else:
            widget.hideTooltip()
        return valid

    cent_iprice = EditableTreeview.ColEntry(TooltipEntry(tree), func_validate=validate_price)
    cent_fprice = EditableTreeview.ColEntry(TooltipEntry(tree), func_validate=validate_price)
    cent_fstate = EditableTreeview.ColEntry(Combobox(tree, values=['', 'Enable', 'Disable'], state='readonly'),
                                            accept_events=('<<ComboboxSelected>>', '<Return>'))

    tree.register_column('Item Price', cent_iprice)
    tree.register_column('Filter Price', cent_fprice)
    tree.register_column('Filter Force State', cent_fstate)


    def init_column(id):
        tree.heading(id, text=id, anchor=W, command=lambda col=id: tree.sort_col(col))

    for col in tree['columns']:
        init_column(col)

    tree.heading('#0', text='ID')
    # tree.heading('Title', text='Title')
    # tree.heading('Item Price', text='Item Price')
    # tree.heading('Filter Price', text='Filter Price')
    # tree.heading('Filter Force State', text='Filter Force State')

    tree.insert('', END, values=('Atziri\'s Disfavour', '1 ex', '* 1', ''), text='_atziri\'s_disfavour')
    tree.insert('', END, values=('Cospri\'s Will', '2 ex', '', ''), text='_cospri\'s_will')
    tree.insert('', END, values=('Vessel of vinktar', '100 chaos', '* 1', ''), text='_vessel_of_vinktar')

    root.geometry("800x600")

    print('col ', tree.column('#2'))

    cmb = Combobox(root, values=['AAAA', 'BBBBB', 'Cremlin'], state='readonly')
    cmb.pack()

    entry = Entry(root, text='ssass')
    entry.pack(side=LEFT)
    # cmb.focus_force()
    # cmb.event_generate('<Down>')

    def print_focus(event=None):
        print(cmb.tk.call('focus'))

    cmb.bind('<FocusIn>', lambda event: print('focus In'))
    cmb.bind('<FocusOut>', print_focus)
    # cmb.focus_force()
    # print_focus()
    print(root.winfo_name())
    print(cmb.winfo_name())
    # lambda event: print('focus out')



    root.mainloop()

