from tkinter.constants import *
from tkinter import Menu, BooleanVar, StringVar, Tk
from tkinter.ttk import Menubutton, Style

import collections

_layout = [
    ('Combobox.border',
    {'children':
        [('Combobox.rightdownarrow', {'side': 'right', 'sticky': 'ns'}),
        ('Button.focus', {'children':
            [('Menubutton.padding',
            {'children':
                [('Menubutton.label', {'sticky': 'nswe'})],
            'sticky': 'nswe'})],
        'sticky': 'nswe'})],
    'sticky': 'nswe'})]

class MultiCombobox(Menubutton):
    def __init__(self, master, kw_vals, default_text='Any', **kwargs):
        super().__init__(master, **kwargs)

        self.default_text = default_text
        self.kw_vals = kw_vals
        self.kw_vals_inv = dict(map(reversed, kw_vals.items()))

        ui_style = Style()
        ui_style.configure('MultiCombobox.TMenubutton', relief=RAISED, padding=3, anchor=CENTER)
        ui_style.layout('MultiCombobox.TMenubutton', _layout)
        self.config(style='MultiCombobox.TMenubutton')

        menu = Menu(self, tearoff=False,
                    activeforeground='SystemHighlightText', activebackground='SystemHighlight',
                    foreground='SystemWindowText', background='SystemWindow',
                    disabledforeground='SystemGrayText', bd=0, activeborderwidth=1)
        self.configure(menu=menu)

        self.any_var = BooleanVar(value=True)
        menu.add_checkbutton(label=default_text, variable=self.any_var,
                             onvalue=True, offvalue=False,
                             command=self.anySelected)

        self.choices = {}
        for i, choice in enumerate(kw_vals):
            self.choices[choice] = BooleanVar()
            # columnbreak = (i+1) % 4 == 0
            columnbreak = False
            menu.add_checkbutton(label=choice, variable=self.choices[choice],
                                 onvalue=True, offvalue=False, columnbreak=columnbreak,
                                 command=self.updateValue)
        self.updateValue()

    def updateValue(self):
        selected = [choice for choice in self.kw_vals if self.choices[choice].get()]

        if selected:
            self.any_var.set(False)
            text = self._list_to_field(selected)
        else:
            self.any_var.set(True)
            text = self.default_text

        self.config(text=text)

    def anySelected(self):
        if self.any_var.get():
            self.set_value()
        else:
            self.any_var.set(True)

    def _list_to_field(self, lst):
        s = None
        for item in lst:
            if not s:
                s = str(item)
            else:
                s += ', ' + str(item)
        return s

    def get_value(self):
        selected = [self.kw_vals[choice] for choice in self.kw_vals if self.choices[choice].get()]
        if selected:
            return selected
        return None

    def set_value(self, vals=None):

        if vals is None:
            vals = []

        for choice in self.choices:
            self.choices[choice].set(False)

        for val in vals:
            try:
                self.choices[self.kw_vals_inv[val]].set(True)
            except KeyError:
                pass

        self.updateValue()

if __name__ == "__main__":
    root = Tk()

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

    mcmb = MultiCombobox(root, ItemTypeOptions)
    mcmb.pack(fill='both', expand='True')

    mcmb.set_value(['prophecy', 'relic', 'unique', 'rare'])
    # Example(root).pack(fill="both", expand=True)
    root.mainloop()


