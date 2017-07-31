from tkinter.constants import *
from tkinter.ttk import Entry

from ui.TooltipEntry import TooltipEntry


class PlaceholderEntry(TooltipEntry):
    def __init__(self, parent, ph_text, ph_style=None, *args, **kw):
        # if 'textvariable' in kw:
        #     self._entry_var = kw['textvariable']
        # else:
        #     self._entry_var = kw['textvariable'] = StringVar()

        super().__init__(parent, *args, **kw)

        if ph_style is None:
            ph_style = self.cget('style')
            if not ph_style:
                ph_style = self.winfo_class()
            ph_style = 'Placeholder.' + ph_style

        self.normal_style = self.cget('style')
        self.ph_style = ph_style
        self.ph_text = ph_text
        self.with_placeholder = False

        self.bind('<FocusIn>', self.onFocusIn, add="+")
        self.bind('<FocusOut>', self.onFocusOut, add="+")
        self.onFocusOut()

    def Reset(self):
        self.delete(0, "end")
        self.onFocusOut()

    def onFocusIn(self, event=None):
        if self.with_placeholder:
            self.delete(0, "end")
            self.config(style=self.normal_style)
            self.with_placeholder = False

    def onFocusOut(self, event=None):
        if self.get() == '':
            self.insert(0, self.ph_text)
            self.config(style=self.ph_style)
            self.with_placeholder = True

    def get_value(self):
        if self.with_placeholder:
            return ''
        return self.get()

    def set_value(self, val):
        self.onFocusIn()
        self.insert(END, val)
        self.onFocusOut()

    def set_state(self, state):
        if state == DISABLED:
            self.onFocusIn()
        else:
            self.onFocusOut()
        self.config(state=state)

    def insert_value(self, index, string):
        self.onFocusIn()
        self.insert(index, string)
        self.onFocusOut()


class PlaceholderEntryOld(Entry):
    def __init__(self, parent, ph_text, ph_style=None, **kw):
        Entry.__init__(self, parent, **kw)
        if ph_style is None:
            ph_style = self.cget('style')
            if not ph_style:
                ph_style = self.winfo_class()
            ph_style = 'Placeholder.' + ph_style

        self.normal_style = self.cget('style')
        self.ph_style = ph_style
        self.ph_text = ph_text
        self.with_placeholder = False

        self.bind('<FocusIn>', self.onFocusIn, add="+")
        self.bind('<FocusOut>', self.onFocusOut, add="+")
        self.onFocusOut()

    def Reset(self):
        self.delete(0, "end")
        self.onFocusOut()

    def onFocusIn(self, event=None):
        if self.with_placeholder:
            self.delete(0, "end")
            self.config(style=self.normal_style)
            self.with_placeholder = False

    def onFocusOut(self, event=None):
        if self.get() == '':
            self.insert(0, self.ph_text)
            self.config(style=self.ph_style)
            self.with_placeholder = True

    def get_value(self):
        if self.with_placeholder:
            return ''
        return self.get()

    def set_value(self, val):
        self.onFocusIn()
        self.insert(END, val)
        self.onFocusOut()

    def set_state(self, state):
        if state == DISABLED:
            self.onFocusIn()
        else:
            self.onFocusOut()
        self.config(state=state)



def add_placeholder_to(entry, placeholder_text, placeholder_style):
    normal_style = entry.cget('style')

    def on_focusin(event, entry=entry):
        if entry.with_placeholder:
            entry.delete(0, "end")
            entry.config(style=normal_style)
            entry.with_placeholder = False

    def on_focusout(event, entry=entry):
        if entry.get() == '':
            entry.insert(0, placeholder_text)
            entry.config(style=placeholder_style)
            entry.with_placeholder = True

    entry.with_placeholder = entry.get() == ''
    if entry.with_placeholder:
        entry.insert(0, placeholder_text)
        entry.config(style=placeholder_style)

    entry.bind('<FocusIn>', on_focusin, add="+")
    entry.bind('<FocusOut>', on_focusout, add="+")

cool_font = None

if __name__ == "__main__":
    from tkinter import Tk
    from tkinter.ttk import Entry, Style, LabelFrame, Label
    import tkinter.font as tkfont
    root = Tk()
    root.configure(padx=10, pady=10)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    login_frame = LabelFrame(root, text="Login", padding=5)
    login_frame.grid(column=0, sticky='nsew')
    # login_frame.pack(padx=10, pady=10)

    label = Label(login_frame, text="User: ")
    label.grid(row=0, column=0, sticky='e')

    # I add a border of 1px width and color #bebebe to the entry using these parameters:
    #  - highlightthickness=1
    #  - highlightbackground="#bebebe"
    #

    ui_style = Style()
    ui_style.configure('Default.TEntry')  #, background='white', highlightbackground="#bebebe", highlightthickness=1, bd=1)

    entry_default_font = tkfont.Font(root=root, name="TkTextFont", exists=True)
    ui_style.configure("Bold.TEntry", font=('Sans', '10', 'bold'))
    entry_default_font = tkfont.Font(name=Style().lookup("TEntry", "font"), exists=True)
    entry_placeholder_font = entry_default_font.copy()
    entry_placeholder_font.config(weight=tkfont.BOLD)

    print(entry_placeholder_font.config())
    cool_font = entry_placeholder_font
    # ui_style.configure('Placeholder.TEntry', foreground='green', font=)

    # self.entry_placeholder_font = entry_placeholder_font

    entry = PlaceholderEntry(login_frame, 'Enter your username..', style='Bold.TEntry')
    print(entry.ph_style)

    # I make the entry a little bit more height using ipady option
    entry.grid(row=0, column=1, ipady=1)

    # add_placeholder_to(entry, 'Enter your username...', 'Placeholder.Default.TEntry')

    label = Label(login_frame, text="Password: ")
    label.grid(row=1, column=0, sticky='e')

    entry = Entry(login_frame, style='Default.TEntry')
    entry.grid(row=1, column=1, ipady=1)

    add_placeholder_to(entry, 'Password...', 'Placeholder.Default.TEntry')

    # Every row has a minimum size
    login_frame.grid_rowconfigure(0, minsize=28)
    login_frame.grid_rowconfigure(1, minsize=28)

    root.mainloop()
