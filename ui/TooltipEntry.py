from tkinter.ttk import Entry

class TooltipEntry(Entry):
    def __init__(self, parent, *args, **kw):
        Entry.__init__(self, parent, *args, **kw)

        self.tooltip = Tooltip2(self, waittime=0, text='', bg='white')  #, pad=(0, 0, 0, 0))

    def showTooltip(self, text=None, pos=None):
        self.tooltip.show(text, pos)

    def hideTooltip(self):
        self.tooltip.hide()

    def destroy(self):
        self.tooltip.hide()
        super().destroy()


from tkinter.ttk import Label
from tkinter import Toplevel, Frame
from tkinter.constants import *

TIP_RIGHT = 'right'
TIP_BELOW = 'below'
TIP_ABOVE = 'above'

class Tooltip:
    '''
    It creates a tooltip for a given widget as the mouse goes on it.

    see:

    https://stackoverflow.com/questions/3221956/
           what-is-the-simplest-way-to-make-tooltips-
           in-tkinter/36221216#36221216

    http://www.daniweb.com/programming/software-development/
           code/484591/a-tooltip-class-for-tkinter

    - Originally written by vegaseat on 2014.09.09.

    - Modified to include a delay time by Victor Zaccardo on 2016.03.25.

    - Modified
        - to correct extreme right and extreme bottom behavior,
        - to stay inside the screen whenever the tooltip might go out on 
          the top but still the screen is higher than the tooltip,
        - to use the more flexible mouse positioning,
        - to add customizable background color, padding, waittime and
          wraplength on creation
      by Alberto Vassena on 2016.11.05.

      Tested on Ubuntu 16.04/16.10, running Python 3.5.2

    TODO: themes styles support
    '''

    def __init__(self, widget,
                 *,
                 bg='#FFFFEA',
                 pad=(5, 3, 5, 3),
                 text='widget info',
                 waittime=400,
                 wraplength=250,
                 pos=TIP_RIGHT):

        self.waittime = waittime  # in miliseconds, originally 500
        self.wraplength = wraplength  # in pixels, originally 180
        self.widget = widget
        self.text = text
        # self.widget.bind("<Enter>", self.onEnter)
        # self.widget.bind("<Leave>", self.onLeave)
        self.widget.bind('<Configure>', self.onConfigure, add='+')
        self.widget.winfo_toplevel().bind('<Configure>', self.onWindowConfigure, add='+')
        # self.widget.bind("<ButtonPress>", self.onLeave, add='+')
        # self.widget.bind("<FocusOut>", self.onLeave, add='+')
        self.bg = bg
        self.pad = pad
        self.pos = pos
        self.id = None
        self.tw = None
        self.win = None

    def onWindowConfigure(self, event):
        if not event.widget.winfo_viewable():
            self.hide()
        else:
            self.updatePosition()


    def onConfigure(self, event=None):
        self.updatePosition()

    def onEnter(self, event=None):
        self.schedule()

    def onLeave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.show)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def show(self, text=None, pos=None):
        self.hide()

        if text is not None:
            self.text = text
        if pos is not None:
            self.pos = pos

        bg = self.bg
        pad = self.pad
        widget = self.widget

        # creates a toplevel window
        self.tw = Toplevel(widget)

        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)

        self.win = Frame(self.tw,
                         background=bg,
                         highlightcolor='red',
                         highlightthickness=2,
                         highlightbackground='red',
                         borderwidth=0)

        label = Label(self.win,
                      text=self.text,
                      justify=LEFT,
                      background=bg,
                      # foreground='blue',
                      # relief=SOLID,
                      borderwidth=0,
                      wraplength=self.wraplength)

        label.grid(padx=(pad[0], pad[2]),
                   pady=(pad[1], pad[3]),
                   sticky=NSEW)
        self.win.grid()

        widget.update_idletasks()

        self.updatePosition()

    def hide(self):
        tw = self.tw
        if tw:
            tw.destroy()
        self.tw = None
        self.win = None

    def updatePosition(self):
        if self.tw:
            x, y = self._tip_pos_calculator(self.widget, self.win)
            self.tw.wm_geometry("+%d+%d" % (x, y))

    def _tip_pos_calculator(self, widget, label,
                               *,
                               tip_delta=(10, 5), pad=(5, 3, 5, 3)):

            w = widget

            s_width, s_height = w.winfo_screenwidth(), w.winfo_screenheight()

            # width, height = (pad[0] + label.winfo_reqwidth() + pad[2],
            #                  pad[1] + label.winfo_reqheight() + pad[3])

            width, height = label.winfo_width(), label.winfo_height()


            # mouse_x, mouse_y = w.winfo_pointerxy()

            # x1, y1 = mouse_x + tip_delta[0], mouse_y + tip_delta[1]
            # x2, y2 = x1 + width, y1 + height
            # print('widget height: {}\ttooltip height: {}'.format(w.winfo_height(), height))

            if self.pos == TIP_BELOW:
                x1, y1 = w.winfo_rootx(), w.winfo_rooty() + w.winfo_height() + tip_delta[1]
            else:
                x1, y1 = w.winfo_rootx() + w.winfo_width() + tip_delta[0], w.winfo_rooty() + (w.winfo_height() - height) / 2

            x2, y2 = x1 + width, y1 + height
            x_delta = x2 - s_width
            if x_delta < 0:
                x_delta = 0
            y_delta = y2 - s_height
            if y_delta < 0:
                y_delta = 0

            offscreen = (x_delta, y_delta) != (0, 0)

            if offscreen:

                if x_delta:
                    # x1 = mouse_x - tip_delta[0] - width
                    x1 = x1 - width - tip_delta[0]*2 - w.winfo_width()
                    # y1 = y1 + w.winfo_height()

                if y_delta:
                    # y1 = mouse_y - tip_delta[1] - height
                    y1 = y1 - height - tip_delta[1]*2


            offscreen_again = y1 < 0  # out on the top

            if offscreen_again:
                # No further checks will be done.

                # TIP:
                # A further mod might automagically augment the
                # wraplength when the tooltip is too high to be
                # kept inside the screen.
                y1 = 0

            return x1, y1



class Tooltip2:

    def __init__(self, widget,
                 *,
                 bg='#FFFFEA',
                 pad=(5, 3, 5, 3),
                 text='widget info',
                 waittime=400,
                 wraplength=500,
                 pos=TIP_RIGHT):

        self.waittime = waittime  # in miliseconds, originally 500
        self.wraplength = wraplength  # in pixels, originally 180
        self.widget = widget
        self.text = text

        self.widget.bind('<Configure>', self.onConfigure, add='+')
        # self.widget.winfo_toplevel().bind('<Configure>', self.onWindowConfigure, add='+')

        self.bg = bg
        self.pad = pad
        self.pos = pos
        self.id = None
        self.win = None
        self.label = None

    def onWindowConfigure(self, event):
        if not event.widget.winfo_viewable():
            self.hide()
        else:
            self.updatePosition()

    def onConfigure(self, event=None):
        self.updatePosition()

    def onEnter(self, event=None):
        self.schedule()

    def onLeave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.show)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def show(self, text=None, pos=None):
        self.hide()

        if text is not None:
            self.text = text
        if pos is not None:
            self.pos = pos

        bg = self.bg
        pad = self.pad
        widget = self.widget

        # self.widget.bind('<Configure>', self.onConfigure, add='+')

        self.win = Frame(self.widget.winfo_toplevel(),
                         background=bg,
                         highlightcolor='red',
                         highlightthickness=2,
                         highlightbackground='red',
                         borderwidth=0)

        self.label = Label(self.win,
                      text=self.text,
                      justify=LEFT,
                      background=bg,
                      # foreground='blue',
                      # relief=SOLID,
                      borderwidth=0,
                      wraplength=self.wraplength)

        self.label.grid(padx=(pad[0], pad[2]),
                   pady=(pad[1], pad[3]),
                   sticky=NSEW)
        # self.win.grid()

        # self.win.place(in_=self.widget, x=0,y=0)
        # widget.update_idletasks()

        self.updatePosition()

    def hide(self):
        if self.win:
            # self.widget.unbind('<Configure>', self.onConfigure)
            self.win.destroy()
            self.win = None

    def updatePosition(self):
        if self.win:
            x, y = self._tip_pos_calculator(self.widget, self.win)
            self.win.place(in_=self.widget, x=x, y=y)

    def _tip_pos_calculator(self, widget, frm, tip_delta=(5, 3)):

            w = widget

            width, height = frm.winfo_width(), frm.winfo_height()

            width = self.label.winfo_reqwidth() + self.pad[0] + self.pad[2] + float(self.win.cget('highlightthickness')) * 2
            height = self.label.winfo_reqheight() + self.pad[1] + self.pad[3] + float(self.win.cget('highlightthickness')) * 2

            if self.pos == TIP_BELOW:
                x1, y1 = 0, w.winfo_height() + tip_delta[1]
            elif self.pos == TIP_ABOVE:
                x1, y1 = 0, -height - tip_delta[1]
            else:
                x1, y1 = w.winfo_width() + tip_delta[0], (w.winfo_height() - height) / 2

            return x1, y1