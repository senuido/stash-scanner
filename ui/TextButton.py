from tkinter import Button


class TextButton(Button):
    def __init__(self, master, *args, **kw):
        super().__init__(master, *args, **kw)

        self._bg = None
        self._hover_bg = None

        self.set_hover_colors(self.cget('background'), self.cget('activebackground'))

    def set_hover_colors(self, bg, hover_bg):
        self._bg = bg
        self._hover_bg = hover_bg

        if self._bg and self._hover_bg:
            self.bind('<Enter>', lambda event: self.config(background=self._hover_bg))
            self.bind('<Leave>', lambda event: self.config(background=self._bg))
        else:
            self.unbind('<Enter>')
            self.unbind('<Leave')