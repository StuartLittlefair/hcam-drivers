# general purpose widgets
from __future__ import print_function, unicode_literals, absolute_import, division
import tkinter as tk
from six.moves import urllib
import threading
import time
import socket
from functools import reduce
import numpy as np

# astropy utilities
from astropy import coordinates as coord
from astropy import units as u
from astropy.time import Time

# internal
from . import get_root, DriverError, tcs
from .logs import Logger, GuiHandler
from .astro import calc_riseset
from .misc import (execCommand, checkSimbad, isRunActive,
                   getRunNumber)


# GENERAL UI WIDGETS
class Boolean(tk.IntVar):
    """
    Defines an object representing one of the boolean configuration
    parameters to allow it to be interfaced with the menubar easily.

    If defined, callback is run with the new value of the flag as its
    argument
    """
    def __init__(self, master, flag, callback=None):
        super(Boolean, self).__init__()
        self.master = master
        # get globals from root
        g = get_root(master).globals

        self.set(g.cpars[flag])
        self.trace('w', self._update)
        self.flag = flag
        self.callback = callback

    def _update(self, *args):
        # get globals from root
        g = get_root(self.master).globals
        if self.get():
            g.cpars[self.flag] = True
        else:
            g.cpars[self.flag] = False
        if self.callback:
            self.callback(g.cpars[self.flag])


class IntegerEntry(tk.Entry):
    """
    Defines an Entry field which only accepts integer input.
    This is the base class for several varieties of integer
    input fields and defines much of the feel to do with holding
    the mouse buttons down etc.
    """

    def __init__(self, master, ival, checker, blank, **kw):
        """
        Parameters
        -----------
        master : tkinter.tk
            enclosing widget
        ival : int
            initial integer value
        checker : callable
            check function that is run on any change to the entry
        blank : boolean
            controls whether the field is allowed to be
            blank. In some cases it makes things easier if
            a blank field is allowed, even if it is technically
            invalid (the latter case requires some other checking)
        kw : dict
            optional keyword arguments that are passed to Entry.
        """
        super(IntegerEntry, self).__init__(master, **kw)
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        self._variable = tk.StringVar()
        self._value = str(int(ival))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank = blank
        self.set_bind()

        # Nasty stuff to do with holding mouse
        # buttons down
        self._leftMousePressed = False
        self._shiftLeftMousePressed = False
        self._rightMousePressed = False
        self._shiftRightMousePressed = False
        self._mouseJustPressed = True

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                int(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns integer value, if possible, None if not.
        """
        try:
            return int(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self._value = str(int(num))
        self._variable.set(self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            int(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        # Arrow keys and enter
        self.bind('<Up>', lambda e: self.add(1))
        self.bind('<Down>', lambda e: self.sub(1))
        self.bind('<Shift-Up>', lambda e: self.add(10))
        self.bind('<Shift-Down>', lambda e: self.sub(10))
        self.bind('<Control-Up>', lambda e: self.add(100))
        self.bind('<Control-Down>', lambda e: self.sub(100))

        # Mouse buttons: bit complex since they don't automatically
        # run in continuous mode like the arrow keys
        self.bind('<ButtonPress-1>', self._leftMouseDown)
        self.bind('<ButtonRelease-1>', self._leftMouseUp)
        self.bind('<Shift-ButtonPress-1>', self._shiftLeftMouseDown)
        self.bind('<Shift-ButtonRelease-1>', self._shiftLeftMouseUp)
        self.bind('<Control-Button-1>', lambda e: self.add(100))

        self.bind('<ButtonPress-3>', self._rightMouseDown)
        self.bind('<ButtonRelease-3>', self._rightMouseUp)
        self.bind('<Shift-ButtonPress-3>', self._shiftRightMouseDown)
        self.bind('<Shift-ButtonRelease-3>', self._shiftRightMouseUp)
        self.bind('<Control-Button-3>', lambda e: self.sub(100))

        self.bind('<Double-Button-1>', self._dadd1)
        self.bind('<Double-Button-3>', self._dsub1)
        self.bind('<Shift-Double-Button-1>', self._dadd10)
        self.bind('<Shift-Double-Button-3>', self._dsub10)
        self.bind('<Control-Double-Button-1>', self._dadd100)
        self.bind('<Control-Double-Button-3>', self._dsub100)

        self.bind('<Enter>', self._enter)

    def _leftMouseDown(self, event):
        self._leftMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _leftMouseUp(self, event):
        if self._leftMousePressed:
            self._leftMousePressed = False
            self.after_cancel(self.after_id)

    def _shiftLeftMouseDown(self, event):
        self._shiftLeftMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _shiftLeftMouseUp(self, event):
        if self._shiftLeftMousePressed:
            self._shiftLeftMousePressed = False
            self.after_cancel(self.after_id)

    def _rightMouseDown(self, event):
        self._rightMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _rightMouseUp(self, event):
        if self._rightMousePressed:
            self._rightMousePressed = False
            self.after_cancel(self.after_id)

    def _shiftRightMouseDown(self, event):
        self._shiftRightMousePressed = True
        self._mouseJustPressed = True
        self._pollMouse()

    def _shiftRightMouseUp(self, event):
        if self._shiftRightMousePressed:
            self._shiftRightMousePressed = False
            self.after_cancel(self.after_id)

    def _pollMouse(self):
        """
        Polls @10Hz, with a slight delay at the
        start.
        """
        if self._mouseJustPressed:
            delay = 300
            self._mouseJustPressed = False
        else:
            delay = 100

        if self._leftMousePressed:
            self.add(1)
            self.after_id = self.after(delay, self._pollMouse)

        if self._shiftLeftMousePressed:
            self.add(10)
            self.after_id = self.after(delay, self._pollMouse)

        if self._rightMousePressed:
            self.sub(1)
            self.after_id = self.after(delay, self._pollMouse)

        if self._shiftRightMousePressed:
            self.sub(10)
            self.after_id = self.after(delay, self._pollMouse)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')

        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<ButtonPress-1>')
        self.unbind('<ButtonRelease-1>')
        self.unbind('<ButtonPress-3>')
        self.unbind('<ButtonRelease-3>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Double-Button-1>')
        self.unbind('<shiftDouble-Button-3>')
        self.unbind('<Control-Double-Button-1>')
        self.unbind('<Control-Double-Button-3>')
        self.unbind('<Enter>')

    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd1(self, event):
        self.add(1)
        return 'break'

    def _dsub1(self, event):
        self.sub(1)
        return 'break'

    def _dadd10(self, event):
        self.add(10)
        return 'break'

    def _dsub10(self, event):
        self.sub(10)
        return 'break'

    def _dadd100(self, event):
        self.add(100)
        return 'break'

    def _dsub100(self, event):
        self.sub(100)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)


class PosInt (IntegerEntry):
    """
    Provide positive or 0 integer input. Basically
    an IntegerEntry with one or two extras.
    """

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e: self.set(0))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < 0:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(max(0, val))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(max(0, val))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < 0:
                return False
            else:
                return True
        except:
            return False


class RangedInt(IntegerEntry):
    """
    Provides range-checked integer input.
    """
    def __init__(self, master, ival, imin, imax, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        imin    -- minimum value
        imax    -- maximum value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        kw      -- keyword arguments
        """
        self.imin = imin
        self.imax = imax
        IntegerEntry.__init__(self, master, ival, checker, blank, **kw)
        self.bind('<Next>', lambda e: self.set(self.imin))
        self.bind('<Prior>', lambda e: self.set(self.imax))

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        IntegerEntry.set_bind(self)
        self.bind('<Next>', lambda e: self.set(self.imin))
        self.bind('<Prior>', lambda e: self.set(self.imax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        IntegerEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = int(value)
                if v < self.imin or v > self.imax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(min(self.imax, max(self.imin, val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.imax, max(self.imin, val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            if v < self.imin or v > self.imax:
                return False
            else:
                return True
        except:
            return False


class RangedMint(RangedInt):
    """
    This is the same as RangedInt but locks to multiples
    """

    def __init__(self, master, ival, imin, imax, mfac, checker, blank, **kw):
        """
        mfac must be class that support 'value()' to return an integer value.
        to allow it to be updated
        """
        self.mfac = mfac
        super(RangedMint, self).__init__(master, ival, imin,
                                         imax, checker, blank, **kw)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_bind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')
        self.bind('<Next>', lambda e: self.set(self._min()))
        self.bind('<Prior>', lambda e: self.set(self._max()))

    def set_unbind(self):
        """
        Sets key bindings -- we need this more than once
        """
        RangedInt.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def add(self, num):
        """
        Adds num to the current value, jumping up the next
        multiple of mfac if the result is not a multiple already
        """
        try:
            val = self.value() + num
        except:
            val = num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk + 1)
            elif num < 0:
                val = chunk*(val // chunk)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value, forcing the result to be within
        range and a multiple of mfac
        """
        try:
            val = self.value() - num
        except:
            val = -num

        chunk = self.mfac.value()
        if val % chunk > 0:
            if num > 0:
                val = chunk*(val // chunk)
            elif num < 0:
                val = chunk*(val // chunk + 1)

        val = max(self._min(), min(self._max(), val))
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = int(self._value)
            chunk = self.mfac.value()
            if v < self.imin or v > self.imax or (v % chunk != 0):
                return False
            else:
                return True
        except:
            return False

    def _min(self):
        chunk = self.mfac.value()
        mval = chunk * (self.imin // chunk)
        return mval + chunk if mval < self.imin else mval

    def _max(self):
        chunk = self.mfac.value()
        return chunk * (self.imax // chunk)


class ListInt(IntegerEntry):
    """
    Provides integer input allowing only a finite list of integers.
    Needed for the binning factors.
    """
    def __init__(self, master, ival, allowed, checker, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        allowed -- list of allowed values. Will be checked for uniqueness
        checker -- command that is run on any change to the entry
        kw      -- keyword arguments
        """
        if ival not in allowed:
            raise DriverError('utils.widgets.ListInt: value = ' + str(ival) +
                              ' not in list of allowed values.')
        if len(set(allowed)) != len(allowed):
            raise DriverError('utils.widgets.ListInt: not all values unique' +
                              ' in allowed list.')

        # we need to maintain an index of which integer has been selected
        self.allowed = allowed
        self.index = allowed.index(ival)
        super(ListInt, self).__init__(master, ival, checker, False, **kw)
        self.set_bind()

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')

        self.bind('<Button-1>', lambda e: self.add(1))
        self.bind('<Button-3>', lambda e: self.sub(1))
        self.bind('<Up>', lambda e: self.add(1))
        self.bind('<Down>', lambda e: self.sub(1))
        self.bind('<Enter>', self._enter)
        self.bind('<Next>', lambda e: self.set(self.allowed[0]))
        self.bind('<Prior>', lambda e: self.set(self.allowed[-1]))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Enter>')
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            v = int(value)
            if v not in self.allowed:
                return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        self.index = max(0, min(len(self.allowed)-1, self.index+num))
        self.set(self.allowed[self.index])

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        self.index = max(0, min(len(self.allowed)-1, self.index-num))
        self.set(self.allowed[self.index])

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        return True


class FloatEntry(tk.Entry):
    """
    Defines an Entry field which only accepts floating point input.
    """

    def __init__(self, master, fval, checker, blank, **kw):
        """
        master  -- enclosing widget
        ival    -- initial integer value
        checker -- command that is run on any change to the entry
        blank   -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid (the latter case requires some other checking)
        kw      -- optional keyword arguments that can be used for
                   an Entry.
        """
        # important to set the value of _variable before tracing it
        # to avoid immediate run of _callback.
        super(FloatEntry, self).__init__(master, **kw)
        self._variable = tk.StringVar()
        self._value = str(float(fval))
        self._variable.set(self._value)
        self._variable.trace("w", self._callback)
        self.config(textvariable=self._variable)
        self.checker = checker
        self.blank = blank
        self.set_bind()

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                float(value)
            return value
        except ValueError:
            return None

    def value(self):
        """
        Returns float value, if possible, None if not.
        """
        try:
            return float(self._value)
        except:
            return None

    def set(self, num):
        """
        Sets the current value equal to num
        """
        self._value = str(float(num))
        self._variable.set(self._value)

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(val)

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(val)

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            float(self._value)
            return True
        except:
            return False

    def enable(self):
        self.configure(state='normal')
        self.set_bind()

    def disable(self):
        self.configure(state='disable')
        self.set_unbind()

    def set_bind(self):
        """
        Sets key bindings.
        """
        self.bind('<Button-1>', lambda e: self.add(0.1))
        self.bind('<Button-3>', lambda e: self.sub(0.1))
        self.bind('<Up>', lambda e: self.add(0.1))
        self.bind('<Down>', lambda e: self.sub(0.1))
        self.bind('<Shift-Up>', lambda e: self.add(1))
        self.bind('<Shift-Down>', lambda e: self.sub(1))
        self.bind('<Control-Up>', lambda e: self.add(10))
        self.bind('<Control-Down>', lambda e: self.sub(10))
        self.bind('<Double-Button-1>', self._dadd)
        self.bind('<Double-Button-3>', self._dsub)
        self.bind('<Shift-Button-1>', lambda e: self.add(1))
        self.bind('<Shift-Button-3>', lambda e: self.sub(1))
        self.bind('<Control-Button-1>', lambda e: self.add(10))
        self.bind('<Control-Button-3>', lambda e: self.sub(10))
        self.bind('<Enter>', self._enter)

    def set_unbind(self):
        """
        Unsets key bindings.
        """
        self.unbind('<Button-1>')
        self.unbind('<Button-3>')
        self.unbind('<Up>')
        self.unbind('<Down>')
        self.unbind('<Shift-Up>')
        self.unbind('<Shift-Down>')
        self.unbind('<Control-Up>')
        self.unbind('<Control-Down>')
        self.unbind('<Double-Button-1>')
        self.unbind('<Double-Button-3>')
        self.unbind('<Shift-Button-1>')
        self.unbind('<Shift-Button-3>')
        self.unbind('<Control-Button-1>')
        self.unbind('<Control-Button-3>')
        self.unbind('<Enter>')

    def _callback(self, *dummy):
        """
        This gets called on any attempt to change the value
        """
        # retrieve the value from the Entry
        value = self._variable.get()

        # run the validation. Returns None if no good
        newvalue = self.validate(value)

        if newvalue is None:
            # Invalid: restores previously stored value
            # no checker run.
            self._variable.set(self._value)

        elif newvalue != value:
            # If the value is different update appropriately
            # Store new value.
            self._value = newvalue
            self._variable.set(self.newvalue)
            if self.checker:
                self.checker(*dummy)
        else:
            # Store new value
            self._value = value
            if self.checker:
                self.checker(*dummy)

    # following are callbacks for bindings
    def _dadd(self, event):
        self.add(0.1)
        return 'break'

    def _dsub(self, event):
        self.sub(0.1)
        return 'break'

    def _enter(self, event):
        self.focus()
        self.icursor(tk.END)


class RangedFloat(FloatEntry):
    """
    Provides range-checked float input.
    """
    def __init__(self, master, fval, fmin, fmax, checker,
                 blank, allowzero=False, **kw):
        """
        master    -- enclosing widget
        fval      -- initial float value
        fmin      -- minimum value
        fmax      -- maximum value
        checker   -- command that is run on any change to the entry
        blank     -- controls whether the field is allowed to be
                   blank. In some cases it makes things easier if
                   a blank field is allowed, even if it is technically
                   invalid.
        allowzero -- if 0 < fmin < 1 input of numbers in the range fmin to 1
                     can be difficult unless 0 is allowed even though it is
                     an invalid value.
        kw        -- keyword arguments
        """
        self.fmin = fmin
        self.fmax = fmax
        super(RangedFloat, self).__init__(master, fval, checker, blank, **kw)
        self.bind('<Next>', lambda e: self.set(self.fmin))
        self.bind('<Prior>', lambda e: self.set(self.fmax))
        self.allowzero = allowzero

    def set_bind(self):
        """
        Sets key bindings -- we need this more than once
        """
        FloatEntry.set_bind(self)
        self.bind('<Next>', lambda e: self.set(self.fmin))
        self.bind('<Prior>', lambda e: self.set(self.fmax))

    def set_unbind(self):
        """
        Unsets key bindings -- we need this more than once
        """
        FloatEntry.set_unbind(self)
        self.unbind('<Next>')
        self.unbind('<Prior>')

    def validate(self, value):
        """
        Applies the validation criteria.
        Returns value, new value, or None if invalid.

        Overload this in derived classes.
        """
        try:
            # trap blank fields here
            if not self.blank or value:
                v = float(value)
                if (self.allowzero and v != 0 and v < self.fmin) or \
                        (not self.allowzero and v < self.fmin) or v > self.fmax:
                    return None
            return value
        except ValueError:
            return None

    def add(self, num):
        """
        Adds num to the current value
        """
        try:
            val = self.value() + num
        except:
            val = num
        self.set(min(self.fmax, max(self.fmin, val)))

    def sub(self, num):
        """
        Subtracts num from the current value
        """
        try:
            val = self.value() - num
        except:
            val = -num
        self.set(min(self.fmax, max(self.fmin, val)))

    def ok(self):
        """
        Returns True if OK to use, else False
        """
        try:
            v = float(self._value)
            if v < self.fmin or v > self.fmax:
                return False
            else:
                return True
        except:
            return False


class TextEntry(tk.Entry):
    """
    Sub-class of Entry for basic text input. Not a lot to
    it but it keeps things neater and it has a check for
    blank entries.
    """
    def __init__(self, master, width, callback=None):
        """
        master  : the widget this gets placed inside
        """        # Define a StringVar, connect it to the callback, if there is one
        self.val = tk.StringVar()
        if callback is not None:
            self.val.trace('w', callback)
        super(TextEntry, self).__init__(
            master,
            textvariable=self.val,
            width=width
        )
        # get globals
        g = get_root(self).globals
        self.config(fg=g.COL['text'], bg=g.COL['main'])
        # Control input behaviour.
        self.bind('<Enter>', lambda e: self.focus())

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Returns value.
        """
        return self.val.set(text)

    def ok(self):
        if self.value() == '' or self.value().isspace():
            return False
        else:
            return True


class Choice(tk.OptionMenu):
    """
    Menu choice class.
    """
    def __init__(self, master, options, initial=None, width=0, checker=None):
        """
        master  : containing widget
        options : list of strings
        initial : the initial one to select. If None will default to the first.
        width   : minimum character width to use. Width set will be large
                  enough for longest option.
        checker : callback to run on any change of selection.
        """

        self.val = tk.StringVar()
        if initial is None:
            self.val.set(options[0])
        else:
            self.val.set(initial)
        super(Choice, self).__init__(master, self.val, *options)
        width = max(width, reduce(max, [len(s) for s in options]))
        g = get_root(self).globals
        self.config(width=width, font=g.ENTRY_FONT)
        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        return self.val.set(choice)

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())


class Expose(RangedFloat):
    """
    Special entry field for exposure times designed to return
    an integer number of 0.1ms increments.
    """
    def __init__(self, master, fval, fmin, fmax, checker, **kw):
        """
        master  -- enclosing widget
        fval    -- initial value, seconds
        fmin    -- minimum value, seconds
        fmax    -- maximum value, seconds
        checker -- command that is run on any change to the entry

        fval, fmin and fmax must be multiples of 0.0001
        """
        if abs(round(10000*fval)-10000*fval) > 1.e-12:
            raise DriverError(
                'utils.widgets.Expose.__init__: fval must be a multiple of 0.0001')
        if abs(round(10000*fmin)-10000*fmin) > 1.e-12:
            raise DriverError(
                'utils.widgets.Expose.__init__: fmin must be a multiple of 0.0001')
        if abs(round(10000*fmax)-10000*fmax) > 1.e-12:
            raise DriverError(
                'utils.widgets.Expose.__init__: fmax must be a multiple of 0.0001')
        super(Expose, self).__init__(master, fval, fmin, fmax, checker, True, **kw)

    def validate(self, value):
        """
        This prevents setting any value more precise than 0.0001
        """
        try:
            # trap blank fields here
            if value:
                v = float(value)
                if (v != 0 and v < self.fmin) or v > self.fmax:
                    return None
                if abs(round(10000*v)-10000*v) > 1.e-12:
                    return None
            return value
        except ValueError:
            return None

    def ivalue(self):
        """
        Returns integer value in units of 0.1ms, if possible, None if not.
        """
        try:
            return int(round(10000*float(self._value)))
        except:
            return None

    def set_min(self, fmin):
        """
        Updates minimum value
        """
        if round(10000*fmin) != 10000*fmin:
            raise DriverError('utils.widgets.Expose.set_min: ' +
                              'fmin must be a multiple of 0.0001')
        self.fmin = fmin
        self.set(self.fmin)


class Radio(tk.Frame):
    """
    Left-to-right radio button class. Lays out buttons in a grid
    from left-to-right. Has a max number of columns after which it
    will jump to left of next row and start over.
    """
    def __init__(self, master, options, ncmax, checker=None,
                 values=None, initial=0):
        """
        master : containing widget
        options : array of option strings, in order. These are the choices
        presented to the user.
        ncmax : max number of columns (flows onto next row if need be)
        checker : callback to be run after any change
        values : array of string values used by the code internally.
        If 'None', the value from 'options' will be used.
        initial : index of initial value to set.
        """
        super(Radio, self).__init__(master)
        # get globals from root widget
        g = get_root(self).globals
        if values is not None and len(values) != len(options):
            raise DriverError('utils.widgets.Radio.__init__: values and ' +
                              'options must have same length')

        self.val = tk.StringVar()
        if values is None:
            self.val.set(options[initial])
        else:
            self.val.set(values[initial])

        row = 0
        col = 0
        self.buttons = []
        for nopt, option in enumerate(options):
            if values is None:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   font=g.ENTRY_FONT, value=option))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            else:
                self.buttons.append(
                    tk.Radiobutton(self, text=option, variable=self.val,
                                   font=g.ENTRY_FONT, value=values[nopt]))
                self.buttons[-1].grid(row=row, column=col, sticky=tk.W)
            col += 1
            if col == ncmax:
                row += 1
                col = 0

        self.checker = checker
        if self.checker is not None:
            self.val.trace('w', self.checker)
        self.options = options

    def value(self):
        return self.val.get()

    def set(self, choice):
        self.val.set(choice)

    def disable(self):
        for b in self.buttons:
            b.configure(state='disable')

    def enable(self):
        for b in self.buttons:
            b.configure(state='normal')

    def getIndex(self):
        """
        Returns the index of the selected choice,
        Throws a ValueError if the set value is not
        one of the options.
        """
        return self.options.index(self.val.get())


class OnOff(tk.Checkbutton):
    """
    On or Off choice
    """
    def __init__(self, master, value, checker=None):
        self.val = tk.IntVar()
        self.val.set(value)
        super(OnOff, self).__init__(master, variable=self.val,
                                    command=checker)

    def __call__(self):
        return self.val.get()

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def set(self, state):
        self.val.set(state)


class Select(tk.OptionMenu):
    """
    Dropdown box menu for selection
    """
    def __init__(self, master, initial_index, options, checker=None):
        self.val = tk.StringVar()
        self.options = options
        self.val.set(options[initial_index])
        super(Select, self).__init__(master, self.val, *options,
                                     command=checker)

    def __call__(self):
        return self.val.get()

    def disable(self):
        self.configure(state='disable')

    def enable(self):
        self.configure(state='normal')

    def set(self, value):
        if value not in self.options:
            raise ValueError('{0} not one of the possible options: {1!r}'.format(
                value, self.options
            ))
        self.val.set(value)


class GuiLogger(Logger, tk.Frame):
    """
    Defines a GUI logger, a combination of Logger and a Frame

     logname : unique name for logger
     root    : the root widget the LabelFrame descends from
     height  : height in pixels
     width   : width in pixels

    """
    def __init__(self, logname, root, height, width):

        # configure the Logger
        Logger.__init__(self, logname)

        # configure the LabelFrame
        tk.Frame.__init__(self, root)

        g = get_root(self).globals
        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        twidget = tk.Text(
            self, height=height, width=width, bg=g.COL['log'],
            yscrollcommand=scrollbar.set)
        twidget.configure(state=tk.DISABLED)
        twidget.pack(side=tk.LEFT)
        scrollbar.config(command=twidget.yview)

        # create and add a handler for the GUI
        self._log.addHandler(GuiHandler(twidget))


class LabelGuiLogger(Logger, tk.LabelFrame):
    """
    Defines a GUI logger, a combination of Logger and a LabelFrame

     logname : unique name for logger
     root    : the root widget the LabelFrame descends from
     height  : height in pixels
     width   : width in pixels
     label   : label for the LabelFrame

    """

    def __init__(self, logname, root, height, width, label):

        # configure the Logger
        Logger.__init__(self, logname)

        # configure the LabelFrame
        tk.LabelFrame.__init__(self, root, text=label)

        g = get_root(self).globals
        scrollbar = tk.Scrollbar(self)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        twidget = tk.Text(
            self, height=height, width=width, bg=g.COL['log'],
            yscrollcommand=scrollbar.set)
        twidget.configure(state=tk.DISABLED)
        twidget.pack(side=tk.LEFT)
        scrollbar.config(command=twidget.yview)

        # create and add a handler for the GUI
        self._log.addHandler(GuiHandler(twidget))


class ActButton(tk.Button):
    """
    Base class for action buttons. This keeps an internal flag
    representing whether the button should be active or not.
    Whether it actually is, might be overridden, but the internal
    flag tracks the (potential) activity status allowing it to be
    reset. The 'expert' flag controls whether the activity status
    will be overridden. The button starts out in non-expert mode by
    default. This can be switched with setExpert, setNonExpert.
    """

    def __init__(self, master, width, callback=None, **kwargs):
        """
        master   : containing widget
        width    : width in characters of the button
        callback : function that is called when button is pressed
        bg       : background colour
        kwargs   : keyword arguments
        """
        super(ActButton, self).__init__(master, fg='black', width=width,
                                        command=self.act, **kwargs)

        # store some attributes. other anc calbback are obvious.
        # _active indicates whether the button should be enabled or disabled
        # _expert indicates whether the activity state should be overridden so
        #         that the button is enabled in any case (if set True)
        self.callback = callback
        self._active = True
        self._expert = False

    def enable(self):
        """
        Enable the button, set its activity flag.
        """
        self.config(state='normal')
        self._active = True

    def disable(self):
        """
        Disable the button, if in non-expert mode;
        unset its activity flag come-what-may.
        """
        if not self._expert:
            self.config(state='disable')
        self._active = False

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        self._expert = True
        self.configure(state='normal')

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carry out the action associated with the button.
        Override in derived classes
        """
        self.callback()


class Ilabel(tk.Label):
    """
    Class to define an information label which uses the same font
    as the entry fields rather than the default font
    """
    def __init__(self, master, **kw):
        super(Ilabel, self).__init__(master, **kw)
        g = get_root(self).globals
        self.config(font=g.ENTRY_FONT)


#
# More HiperCam specific, but still general purpose widgets
#
class Stop(ActButton):
    """
    Class defining the 'Stop' button's operation
    """

    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        super(Stop, self).__init__(master, width, text='Stop')
        g = get_root(self).globals
        self.config(bg=g.COL['stop'])

        # flags to help with stopping in background
        self.stopped_ok = True
        self.stopping = False

    def enable(self):
        """
        Enable the button.
        """
        ActButton.enable(self)
        g = get_root(self).globals
        self.config(bg=g.COL['stop'])

    def disable(self):
        """
        Disable the button, if in non-expert mode.
        """
        ActButton.disable(self)
        g = get_root(self).globals
        if self._expert:
            self.config(bg=g.COL['stop'])
        else:
            self.config(bg=g.COL['stopD'])

    def setExpert(self):
        """
        Turns on 'expert' status whereby the button is always enabled,
        regardless of its activity status.
        """
        ActButton.setExpert(self)
        g = get_root(self).globals
        self.config(bg=g.COL['stop'])

    def setNonExpert(self):
        """
        Turns off 'expert' status whereby to allow a button to be disabled
        """
        self._expert = False
        if self._active:
            self.enable()
        else:
            self.disable()

    def act(self):
        """
        Carries out the action associated with Stop button
        """
        g = get_root(self).globals
        g.clog.debug('Stop pressed')

        def stop_in_background():
            try:
                self.stopping = True
                if execCommand(g, 'stop'):
                    # Report that run has stopped
                    g.clog.info('Run stopped')
                    self.stopped_ok = True
                else:
                    g.clog.warn('Failed to stop run')
                    self.stopped_ok = False
                self.stopping = False
            except Exception as err:
                g.clog.warn('Failed to stop run. Error = ' + str(err))
                self.stopping = False
                self.stopped_ok = False

        # stopping can take a while during which the GUI freezes so run in
        # background.
        t = threading.Thread(target=stop_in_background)
        t.daemon = True
        t.start()

    def check(self):
        """
        Checks the status of the stop exposure command
        This is run in background and can take a few seconds
        """
        g = get_root(self).globals
        if self.stopped_ok:
            # Exposure stopped OK; modify buttons
            self.disable()
            g.observe.start.enable()
            g.setup.powerOn.disable()
            g.setup.powerOff.enable()

            # Stop exposure meter
            g.info.timer.stop()
            return True

        elif self.stopping:
            # Exposure in process of stopping
            # Disable lots of buttons
            self.disable()
            g.observe.start.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()

            # wait a second before trying again
            self.after(1000, self.check)

        else:
            self.enable()
            g.observe.start.disable()
            g.setup.powerOn.disable()
            g.setup.powerOff.disable()
            return False


class Target(tk.Frame):
    """
    Class wrapping up what is needed for a target name which
    is an entry field and a verification button. The verification
    button checks for simbad recognition and goes green or red
    according to the results. If no check has been made, it has
    a default colour.
    """
    def __init__(self, master, callback=None):
        super(Target, self).__init__(master)

        g = get_root(self).globals

        # Entry field, linked to a StringVar which is traced for
        # any modification
        self.val = tk.StringVar()
        self.val.trace('w', self.modver)
        self.entry = tk.Entry(
            self, textvariable=self.val, fg=g.COL['text'],
            bg=g.COL['main'], width=25)
        self.entry.bind('<Enter>', lambda e: self.entry.focus())

        # Verification button which accesses simbad to see if
        # the target is recognised.
        self.verify = tk.Button(
            self, fg='black', width=8, text='Verify',
            bg=g.COL['main'], command=self.act)
        self.entry.pack(side=tk.LEFT, anchor=tk.W)
        self.verify.pack(side=tk.LEFT, anchor=tk.W, padx=5)
        self.verify.config(state='disable')
        # track successed and failures
        self.successes = []
        self.failures = []
        self.callback = callback

    def value(self):
        """
        Returns value.
        """
        return self.val.get()

    def set(self, text):
        """
        Sets value.
        """
        return self.val.set(text)

    def disable(self):
        self.entry.configure(state='disable')
        g = get_root(self).globals
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['startD'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stopD'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
        else:
            self.verify.config(bg=g.COL['main'])
        self.verify.config(state='disable')

    def enable(self):
        self.entry.configure(state='normal')
        g = get_root(self).globals
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['start'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stop'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
        else:
            self.verify.config(bg=g.COL['main'])
        self.verify.config(state='normal')

    def ok(self):
        if self.val.get() == '' or self.val.get().isspace():
            return False
        else:
            return True

    def modver(self, *args):
        """
        Switches colour of verify button
        """
        g = get_root(self).globals
        if self.ok():
            tname = self.val.get()
            if tname in self.successes:
                # known to be in simbad
                self.verify.config(bg=g.COL['start'])
            elif tname in self.failures:
                # known not to be in simbad
                self.verify.config(bg=g.COL['stop'])
            else:
                # not known whether in simbad
                self.verify.config(bg=g.COL['main'])
            self.verify.config(state='normal')
        else:
            self.verify.config(bg=g.COL['main'])
            self.verify.config(state='disable')

        if self.callback is not None:
            self.callback()

    def act(self):
        """
        Carries out the action associated with Verify button
        """
        tname = self.val.get()
        g = get_root(self).globals
        g.clog.info('Checking ' + tname + ' in simbad')
        try:
            ret = checkSimbad(g, tname)
            if len(ret) == 0:
                self.verify.config(bg=g.COL['stop'])
                g.clog.warn('No matches to "' + tname + '" found.')
                if tname not in self.failures:
                    self.failures.append(tname)
            elif len(ret) == 1:
                self.verify.config(bg=g.COL['start'])
                g.clog.info(tname + ' verified OK in simbad')
                g.clog.info('Primary simbad name = ' + ret[0]['Name'])
                if tname not in self.successes:
                    self.successes.append(tname)
            else:
                g.clog.warn('More than one match to "' + tname + '" found')
                self.verify.config(bg=g.COL['stop'])
                if tname not in self.failures:
                    self.failures.append(tname)
        except urllib.error.URLError:
            g.clog.warn('Simbad lookup timed out')
        except socket.timeout:
            g.clog.warn('Simbad lookup timed out')


class NGCReset(ActButton):
    """
    Class defining the 'NGC Reset' button
    """
    def __init__(self, master, width):
        """
        master   : containing widget
        width    : width of button
        """
        super(NGCReset, self).__init__(master, width, text='NGC Reset')

    def act(self):
        """
        Carries out the action associated with the System Reset
        """
        g = get_root(self).globals
        g.clog.debug('NGC Reset pressed')

        if execCommand(g, 'reset'):
            g.clog.info('NGC Reset succeeded')

            # alter buttons here
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.powerOn.enable()
            g.setup.powerOff.disable()
            return True
        else:
            g.clog.warn('NGC Reset failed')
            return False


class PowerOn(ActButton):
    """
    Class defining the 'Power on' button's operation
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        super(PowerOn, self).__init__(master, width, text='Power on')

    def act(self):
        """
        Power on action
        """
        g = get_root(self).globals
        g.clog.debug('Power on pressed')

        if execCommand(g, 'online'):
            g.clog.info('Power on successful')
            g.cpars['eso_server_online'] = True
            # change other buttons
            self.disable()
            g.observe.start.enable()
            g.observe.stop.disable()
            g.setup.powerOff.enable()

            try:
                # now check the run number -- lifted from Java code; the wait
                # for the power on application to finish may not be needed
                n = 0
                while isRunActive(g) and n < 5:
                    n += 1
                    time.sleep(1)

                if isRunActive(g):
                    g.clog.warn('Timed out waiting for ESO server to come online; ' +
                                'cannot initialise run number. ' +
                                'Tell spl if this happens')
                else:
                    g.info.run.configure(text='{0:03d}'.format(getRunNumber(g, True)))
            except Exception as err:
                g.clog.warn('Failed to determine run number at start of run')
                g.clog.warn(str(err))
                g.info.run.configure(text='UNDEF')
            return True
        else:
            g.clog.warn('Power on failed\n')
            return False


class PowerOff(ActButton):
    """
    Class defining the 'Power off' button's operation
    """

    def __init__(self, master, width):
        """
        master  : containing widget
        width   : width of button
        """
        super(PowerOff, self).__init__(master, width, text='Power off')
        self.disable()

    def act(self):
        """
        Power off action
        """
        g = get_root(self).globals
        g.clog.debug('Power off pressed')

        if execCommand(g, 'off'):

            g.clog.info('ESO server idle and child processes quit')

            # alter buttons
            self.disable()
            g.observe.start.disable()
            g.observe.stop.disable()
            g.setup.powerOn.enable()
            return True
        else:
            g.clog.warn('Power off failed')
            return False


class InstSetup(tk.LabelFrame):
    """
    Instrument setup frame.
    """

    def __init__(self, master):
        """
        master -- containing widget
        """
        super(InstSetup, self).__init__(master, text='Instrument setup',
                                        padx=10, pady=10)

        # Define all buttons
        width = 17
        self.ngcReset = NGCReset(self, width)
        self.powerOn = PowerOn(self, width)
        self.powerOff = PowerOff(self, width)

        # set which buttons are presented and where they go
        self.setExpertLevel()

    def setExpertLevel(self):
        """
        Set expert level
        """
        g = get_root(self).globals
        level = g.cpars['expert_level']

        # first define which buttons are visible
        if level == 0:
            # simple layout
            self.ngcReset.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()

            # then re-grid the two simple ones
            self.powerOn.grid(row=0, column=0)
            self.powerOff.grid(row=0, column=1)

        elif level == 1 or level == 2:
            # first remove all possible buttons
            self.ngcReset.grid_forget()
            self.powerOn.grid_forget()
            self.powerOff.grid_forget()

            # restore detailed layout
            self.powerOn.grid(row=0, column=0)
            self.powerOff.grid(row=1, column=0)
            self.ngcReset.grid(row=0, column=1)

        # now set whether buttons are permanently enabled or not
        if level == 0 or level == 1:
            self.ngcReset.setNonExpert()
            self.powerOn.setNonExpert()
            self.powerOff.setNonExpert()

        elif level == 2:
            self.ngcReset.setExpert()
            self.powerOn.setExpert()
            self.powerOff.setExpert()


class Switch(tk.Frame):
    """
    Frame sub-class to switch between setup, focal plane slide
    and observing frames. Provides radio buttons and hides / shows
    respective frames
    """
    def __init__(self, master):
        """
        master : containing widget
        """
        super(Switch, self).__init__(master)

        self.val = tk.StringVar()
        self.val.set('Setup')
        self.val.trace('w', self._changed)

        g = get_root(self).globals
        tk.Radiobutton(self, text='Setup', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Setup').grid(row=0, column=0, sticky=tk.W)
        tk.Radiobutton(self, text='Observe', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Observe').grid(row=0, column=1, sticky=tk.W)
        tk.Radiobutton(self, text='Focal plane slide', variable=self.val,
                       font=g.ENTRY_FONT,
                       value='Focal plane slide').grid(row=0, column=2,
                                                       sticky=tk.W)

    def _changed(self, *args):
        g = get_root(self).globals
        if self.val.get() == 'Setup':
            g.setup.pack(anchor=tk.W, pady=10)
            g.fpslide.pack_forget()
            g.observe.pack_forget()

        elif self.val.get() == 'Focal plane slide':
            g.setup.pack_forget()
            g.fpslide.pack(anchor=tk.W, pady=10)
            g.observe.pack_forget()

        elif self.val.get() == 'Observe':
            g.setup.pack_forget()
            g.fpslide.pack_forget()
            g.observe.pack(anchor=tk.W, pady=10)

        else:
            raise DriverError('Unrecognised Switch value')


class ExpertMenu(tk.Menu):
    """
    Provides a menu to select the level of expertise wanted
    when interacting with a control GUI. This setting might
    be used to hide buttons for instance according to
    the status of others, etc. Use ExpertMenu.indices
    to pass a set of indices of the master menu which get
    enabled or disabled according to the expert level (disabled
    at level 0, otherwise enabled)
    """
    def __init__(self, master, *args):
        """
        master   -- the containing widget, e.g. toolbar menu
        args     -- other objects that have a 'setExpertLevel()' method.
        """
        super(ExpertMenu, self).__init__(master, tearoff=0)
        g = get_root(self).globals

        self.val = tk.IntVar()
        self.val.set(g.cpars['expert_level'])
        self.val.trace('w', self._change)
        self.add_radiobutton(label='Level 0', value=0, variable=self.val)
        self.add_radiobutton(label='Level 1', value=1, variable=self.val)
        self.add_radiobutton(label='Level 2', value=2, variable=self.val)
        self.args = args
        self.root = master
        self.indices = []

    def _change(self, *args):
        g = get_root(self).globals
        g.cpars['expert_level'] = self.val.get()
        for arg in self.args:
            arg.setExpertLevel()
        for index in self.indices:
            if g.cpars['expert_level']:
                self.root.entryconfig(index, state=tk.NORMAL)
            else:
                self.root.entryconfig(index, state=tk.DISABLED)


class Timer(tk.Label):
    """
    Run Timer class. Updates @10Hz, checks
    run status @1Hz. Switches button statuses
    when the run stops.
    """
    def __init__(self, master):
        super(Timer, self).__init__(master, text='{0:<d} s'.format(0))
        g = get_root(self).globals
        self.config(font=g.ENTRY_FONT)
        self.id = None
        self.count = 0

    def start(self):
        """
        Starts the timer from zero
        """
        self.startTime = time.time()
        self.configure(text='{0:<d} s'.format(0))
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock, checks
        run status @1Hz to reduce load on servers.
        """
        g = get_root(self).globals
        try:
            self.count += 1
            delta = int(round(time.time() - self.startTime))
            self.configure(text='{0:<d} s'.format(delta))

            if self.count % 10 == 0:
                if not isRunActive(g):
                    g.observe.start.enable()
                    g.observe.stop.disable()
                    g.setup.ngcReset.enable()
                    g.setup.powerOn.disable()
                    g.setup.powerOff.enable()
                    g.clog.info('Run stopped')
                    self.stop()
                    return

        except Exception as err:
            if self.count % 100 == 0:
                g.clog.warn('Timer.update: error = ' + str(err))

        self.id = self.after(100, self.update)

    def stop(self):
        if self.id is not None:
            self.after_cancel(self.id)
        self.id = None


class InfoFrame(tk.LabelFrame):
    """
    Information frame: run number, exposure time, etc.
    """
    def __init__(self, master):
        tk.LabelFrame.__init__(self, master,
                               text='Current run & telescope status', padx=4, pady=4)

        self.run = Ilabel(self, text='UNDEF')
        self.frame = Ilabel(self, text='UNDEF')
        self.timer = Timer(self)
        self.cadence = Ilabel(self, text='UNDEF')
        self.duty = Ilabel(self, text='UNDEF')
        self.ra = Ilabel(self, text='UNDEF')
        self.dec = Ilabel(self, text='UNDEF')
        self.alt = Ilabel(self, text='UNDEF')
        self.az = Ilabel(self, text='UNDEF')
        self.airmass = Ilabel(self, text='UNDEF')
        self.ha = Ilabel(self, text='UNDEF')
        self.pa = Ilabel(self, text='UNDEF')
        self.focus = Ilabel(self, text='UNDEF')
        self.mdist = Ilabel(self, text='UNDEF')
        self.fpslide = Ilabel(self, text='UNDEF')
        self.honey = Ilabel(self, text='UNDEF')

        # left-hand side
        tk.Label(self, text='Run:').grid(row=0, column=0, padx=5, sticky=tk.W)
        self.run.grid(row=0, column=1, padx=5, sticky=tk.W)

        tk.Label(self, text='Frame:').grid(row=1, column=0, padx=5, sticky=tk.W)
        self.frame.grid(row=1, column=1, padx=5, sticky=tk.W)

        tk.Label(self, text='Exposure:').grid(row=2, column=0, padx=5, sticky=tk.W)
        self.timer.grid(row=2, column=1, padx=5, sticky=tk.W)

        tk.Label(self, text='Cadence:').grid(row=3, column=0, padx=5, sticky=tk.W)
        self.cadence.grid(row=3, column=1, padx=5, sticky=tk.W)

        tk.Label(self, text='Duty cycle:').grid(row=4, column=0, padx=5,
                                                sticky=tk.W)
        self.duty.grid(row=4, column=1, padx=5, sticky=tk.W)

        # middle
        tk.Label(self, text='RA:').grid(row=0, column=3, padx=5, sticky=tk.W)
        self.ra.grid(row=0, column=4, padx=5, sticky=tk.W)

        tk.Label(self, text='Dec:').grid(row=1, column=3, padx=5, sticky=tk.W)
        self.dec.grid(row=1, column=4, padx=5, sticky=tk.W)

        tk.Label(self, text='Alt:').grid(row=2, column=3, padx=5, sticky=tk.W)
        self.alt.grid(row=2, column=4, padx=5, sticky=tk.W)

        tk.Label(self, text='Az:').grid(row=3, column=3, padx=5, sticky=tk.W)
        self.az.grid(row=3, column=4, padx=5, sticky=tk.W)

        tk.Label(self, text='Airm:').grid(row=4, column=3, padx=5, sticky=tk.W)
        self.airmass.grid(row=4, column=4, padx=5, sticky=tk.W)

        tk.Label(self, text='HA:').grid(row=5, column=3, padx=5, sticky=tk.W)
        self.ha.grid(row=5, column=4, padx=5, sticky=tk.W)

        # right-hand side
        tk.Label(self, text='PA:').grid(row=0, column=6, padx=5, sticky=tk.W)
        self.pa.grid(row=0, column=7, padx=5, sticky=tk.W)

        tk.Label(self, text='Focus:').grid(row=1, column=6, padx=5, sticky=tk.W)
        self.focus.grid(row=1, column=7, padx=5, sticky=tk.W)

        tk.Label(self, text='Mdist:').grid(row=2, column=6, padx=5, sticky=tk.W)
        self.mdist.grid(row=2, column=7, padx=5, sticky=tk.W)

        tk.Label(self, text='FP slide:').grid(row=3, column=6, padx=5, sticky=tk.W)
        self.fpslide.grid(row=3, column=7, padx=5, sticky=tk.W)

        tk.Label(self, text='CCD temp:').grid(row=4, column=6, padx=5, sticky=tk.W)
        self.honey.grid(row=4, column=7, padx=5, sticky=tk.W)

        # these are used to judge whether we are tracking or not
        self.coo_old = coord.SkyCoord(0, 0, unit=(u.deg, u.deg))
        self.pa_old = 0*u.deg
        self.tracking = False

        # start
        self.count = 0
        self.update()

    def update(self):
        """
        Updates run & tel status window. Runs
        once every 2 seconds.
        """
        g = get_root(self).globals

        if g.astro is None or g.fpslide is None:
            self.after(100, self.update)
            return

        try:

            if g.cpars['tcs_on']:
                if g.cpars['telins_name'] == 'WHT-HICAM':
                    try:
                        # Poll TCS for ra,dec etc.
                        ra, dec, pa, focus, tracking = tcs.getWhtTcs()

                        # format ra, dec as HMS
                        coo = coord.SkyCoord(ra, dec, unit=(u.deg, u.deg))
                        ratxt = coo.ra.to_string(sep=':', unit=u.hour)
                        dectxt = coo.dec.to_string(sep=':', unit=u.deg, alwayssign=True)
                        self.ra.configure(text=ratxt)
                        self.dec.configure(text=dectxt)

                        # wrap pa from 0 to 360
                        pa = coord.Longitude(pa*u.deg)
                        self.pa.configure(text='{0:6.2f}'.format(pa.value))

                        # check for significant changes in position to flag
                        # tracking failures. I have removed a test of tflag
                        # to be True because the telescope often switches to
                        # "slewing" status even when nominally tracking.
                        if (coo.separation(self.coo_old) < 4*u.arcsec):
                            self.tracking = True
                            self.ra.configure(bg=g.COL['main'])
                            self.dec.configure(bg=g.COL['main'])
                        else:
                            self.tracking = False
                            self.ra.configure(bg=g.COL['warn'])
                            self.dec.configure(bg=g.COL['warn'])

                        # check for changing sky PA
                        if abs(pa-self.pa_old) > 0.1*u.deg:
                            self.pa.configure(bg=g.COL['warn'])
                        else:
                            self.pa.configure(bg=g.COL['main'])

                        # store current values for comparison with next
                        self.coo_old = coo
                        self.pa_old = pa

                        # set focus
                        self.focus.configure(text='{0:+5.2f}'.format(focus))

                        # Calculate most of the
                        # stuff that we don't get from the telescope
                        now = Time.now()
                        lst = now.sidereal_time(kind='mean',
                                                longitude=g.astro.obs.longitude)
                        ha = coo.ra.hourangle*u.hourangle - lst
                        hatxt = ha.wrap_at(12*u.hourangle).to_string(sep=':', precision=0)
                        self.ha.configure(text=hatxt)

                        altaz_frame = coord.AltAz(obstime=now, location=g.astro.obs)
                        altaz = coo.transform_to(altaz_frame)
                        self.alt.configure(text='{0:<4.1f}'.format(altaz.alt.value))
                        self.az.configure(text='{0:<5.1f}'.format(altaz.az.value))
                        # set airmass
                        self.airmass.configure(text='{0:<4.2f}'.format(altaz.secz))

                        # distance to the moon. Warn if too close
                        # (configurable) to it.
                        md = coord.get_moon(now, g.astro.obs).separation(coo)
                        self.mdist.configure(text='{0:<7.2f}'.format(md.value))
                        if md < g.cpars['mdist_warn']*u.deg:
                            self.mdist.configure(bg=g.COL['warn'])
                        else:
                            self.mdist.configure(bg=g.COL['main'])

                    except Exception as err:
                        self.ra.configure(text='UNDEF')
                        self.dec.configure(text='UNDEF')
                        self.pa.configure(text='UNDEF')
                        self.ha.configure(text='UNDEF')
                        self.alt.configure(text='UNDEF')
                        self.az.configure(text='UNDEF')
                        self.airmass.configure(text='UNDEF')
                        self.mdist.configure(text='UNDEF')
                        g.clog.warn('TCS error: ' + str(err))
                else:
                    g.clog.debug('TCS error: could not recognise ' +
                                 g.cpars['telins_name'])

            if g.cpars['hcam_server_on'] and \
               g.cpars['eso_server_online']:

                # get run number (set by the 'Start' button')
                try:
                    # if no run is active, get run number from
                    # hipercam server
                    if not isRunActive(g):
                        run = getRunNumber(g, True)
                        self.run.configure(text='{0:03d}'.format(run))

                    # get the value of the run being displayed, regardless of
                    # whether we just managed to update it
                    rtxt = self.run.cget('text')

                    # if the value comes back as undefined, try to work out
                    # the run number from the hipercam server
                    # TODO: implement this when server is finalised
                    if rtxt == 'UNDEF':
                        pass
                    else:
                        run = int(rtxt)

                    # OK, we have managed to get the run number
                    # rstr = 'run{0:03d}'.format(run)

                    # Find the number of frames in this run
                    # TODO: implement this when server is finalised
                    try:
                        pass
                    except Exception as err:
                        if err.code == 404:
                            self.frame.configure(text='0')
                        else:
                            g.clog.debug('Error occurred trying to set frame')
                            self.frame.configure(text='UNDEF')

                except Exception as err:
                    g.clog.debug('Error trying to set run: ' + str(err))

            # get the slide position
            # poll at 5x slower rate than the frame
            if self.count % 5 == 0 and g.cpars['focal_plane_slide_on']:
                try:
                    pos_ms, pos_mm, pos_px = g.fpslide.slide.return_position()
                    self.fpslide.configure(text='{0:d}'.format(
                        int(round(pos_px))))
                    if pos_px < 1050.:
                        self.fpslide.configure(bg=g.COL['warn'])
                    else:
                        self.fpslide.configure(bg=g.COL['main'])
                except Exception as err:
                    g.clog.warn('Slide error: ' + str(err))
                    self.fpslide.configure(text='UNDEF')
                    self.fpslide.configure(bg=g.COL['warn'])

            # get the CCD temperature poll at 5x slower rate than the frame
            # TODO: implement when honeywell is set up
            if self.count % 5 == 0 and g.cpars['ccd_temperature_on']:
                try:
                    raise NotImplementedError('Honeywell not working yet')
                except Exception as err:
                    g.clog.warn(str(err))
                    self.honey.configure(text='UNDEF')
                    self.honey.configure(bg=g.COL['warn'])

        except Exception as err:
            # this is a safety catchall trap as it is important
            # that this routine keeps going
            g.clog.warn('Unexpected error: ' + str(err))

        # run every 2 seconds
        self.count += 1
        self.after(2000, self.update)


class AstroFrame(tk.LabelFrame):
    """
    Astronomical information frame
    """
    def __init__(self, master):
        super(AstroFrame, self).__init__(master, padx=2, pady=2, text='Time & Sky')

        # times
        self.mjd = Ilabel(self)
        self.utc = Ilabel(self, width=9, anchor=tk.W)
        self.lst = Ilabel(self)

        # sun info
        self.sunalt = Ilabel(self, width=11, anchor=tk.W)
        self.riset = Ilabel(self)
        self.lriset = Ilabel(self)
        self.astro = Ilabel(self)

        # moon info
        self.moonra = Ilabel(self)
        self.moondec = Ilabel(self)
        self.moonalt = Ilabel(self)
        self.moonphase = Ilabel(self)

        # observatory info
        g = get_root(self).globals
        tins = g.TINS[g.cpars['telins_name']]
        lat = tins['latitude']
        lon = tins['longitude']
        elevation = tins['elevation']
        self.obs = coord.EarthLocation.from_geodetic(
            lon*u.deg,
            lat*u.deg,
            elevation*u.m
        )
        # report back to the user
        g.clog.info('Tel/ins = ' + g.cpars['telins_name'])
        g.clog.info('Longitude = ' + str(tins['longitude']) + ' E')
        g.clog.info('Latitude = ' + str(tins['latitude']) + ' N')
        g.clog.info('Elevation = ' + str(tins['elevation']) + ' m')

        # arrange time info
        tk.Label(self, text='MJD:').grid(
            row=0, column=0, padx=2, pady=3, sticky=tk.W)
        self.mjd.grid(row=0, column=1, columnspan=2, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='UTC:').grid(
            row=0, column=3, padx=2, pady=3, sticky=tk.W)
        self.utc.grid(row=0, column=4, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='LST:').grid(
            row=0, column=5, padx=2, pady=3, sticky=tk.W)
        self.lst.grid(row=0, column=6, padx=2, pady=3, sticky=tk.W)

        # arrange solar info
        tk.Label(self, text='Sun:').grid(
            row=1, column=0, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='Alt:').grid(
            row=1, column=1, padx=2, pady=3, sticky=tk.W)
        self.sunalt.grid(row=1, column=2, padx=2, pady=3, sticky=tk.W)
        self.lriset.grid(row=1, column=3, padx=2, pady=3, sticky=tk.W)
        self.riset.grid(row=1, column=4, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='At -18:').grid(
            row=1, column=5, padx=2, pady=3, sticky=tk.W)
        self.astro.grid(row=1, column=6, padx=2, pady=3, sticky=tk.W)

        # arrange moon info
        tk.Label(self, text='Moon:').grid(
            row=2, column=0, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='RA:').grid(
            row=2, column=1, padx=2, pady=3, sticky=tk.W)
        self.moonra.grid(row=2, column=2, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='Dec:').grid(row=3, column=1, padx=2, sticky=tk.W)
        self.moondec.grid(row=3, column=2, padx=2, sticky=tk.W)
        tk.Label(self, text='Alt:').grid(
            row=2, column=3, padx=2, pady=3, sticky=tk.W)
        self.moonalt.grid(row=2, column=4, padx=2, pady=3, sticky=tk.W)
        tk.Label(self, text='Phase:').grid(row=3, column=3, padx=2, sticky=tk.W)
        self.moonphase.grid(row=3, column=4, padx=2, sticky=tk.W)

        # parameters used to reduce re-calculation of sun rise etc, and
        # to provide info for other widgets
        self.lastRiset = Time.now()
        self.lastAstro = Time.now()
        self.counter = 0

        # start
        self.update()

    def update(self):
        """
        Updates @ 10Hz to give smooth running clock.
        """

        try:

            # update counter
            self.counter += 1
            g = get_root(self).globals

            # current time
            now = Time.now()

            # configure times
            self.utc.configure(text=now.datetime.strftime('%H:%M:%S'))
            self.mjd.configure(text='{0:11.5f}'.format(now.mjd))
            lst = now.sidereal_time(kind='mean', longitude=self.obs.longitude)
            self.lst.configure(text=lst.to_string(sep=':', precision=0))

            if self.counter % 600 == 1:
                # only re-compute Sun & Moon info once every 600 calls
                altaz_frame = coord.AltAz(obstime=now, location=self.obs)
                sun = coord.get_sun(now)
                sun_aa = sun.transform_to(altaz_frame)
                moon = coord.get_moon(now, self.obs)
                moon_aa = moon.transform_to(altaz_frame)
                elongation = sun.separation(moon)
                moon_phase_angle = np.arctan2(sun.distance*np.sin(elongation),
                                              moon.distance - sun.distance*np.cos(elongation))
                moon_phase = (1 + np.cos(moon_phase_angle))/2.0

                self.sunalt.configure(
                    text='{0:+03d} deg'.format(int(sun_aa.alt.deg))
                )
                self.moonra.configure(
                    text=moon.ra.to_string(unit='hour', sep=':', precision=0)
                )
                self.moondec.configure(
                    text=moon.dec.to_string(unit='deg', sep=':', precision=0)
                )
                self.moonalt.configure(text='{0:+03d} deg'.format(
                        int(moon_aa.alt.deg)
                ))
                self.moonphase.configure(text='{0:02d} %'.format(
                        int(100.*moon_phase.value)
                ))

                if (now > self.lastRiset and now > self.lastAstro):
                    # Only re-compute rise and setting times when necessary,
                    # and only re-compute when both rise/set and astro
                    # twilight times have gone by

                    # For sunrise and set we set the horizon down to match a
                    # standard amount of refraction at the horizon and subtract size of disc
                    horizon = -64*u.arcmin
                    sunset = calc_riseset(now, 'sun', self.obs, 'next', 'setting', horizon)
                    sunrise = calc_riseset(now, 'sun', self.obs, 'next', 'rising', horizon)

                    # Astro twilight: geometric centre at -18 deg
                    horizon = -18*u.deg
                    astroset = calc_riseset(now, 'sun', self.obs, 'next', 'setting', horizon)
                    astrorise = calc_riseset(now, 'sun', self.obs, 'next', 'rising', horizon)

                    if sunrise > sunset:
                        # In the day time we report the upcoming sunset and
                        # end of evening twilight
                        self.lriset.configure(text='Sets:', font=g.DEFAULT_FONT)
                        self.lastRiset = sunset
                        self.lastAstro = astroset

                    elif astrorise > astroset and astrorise < sunrise:
                        # During evening twilight, we report the sunset just
                        # passed and end of evening twilight
                        self.lriset.configure(text='Sets:', font=g.DEFAULT_FONT)
                        horizon = -64*u.arcmin
                        self.lastRiset = calc_riseset(now, 'sun', self.obs, 'previous', 'setting', horizon)
                        self.lastAstro = astroset

                    elif astrorise > astroset and astrorise < sunrise:
                        # During night, report upcoming start of morning
                        # twilight and sunrise
                        self.lriset.configure(text='Rises:',
                                              font=g.DEFAULT_FONT)
                        horizon = -64*u.arcmin
                        self.lastRiset = sunrise
                        self.lastAstro = astrorise

                    else:
                        # During morning twilight report start of twilight
                        # just passed and upcoming sunrise
                        self.lriset.configure(text='Rises:',
                                              font=g.DEFAULT_FONT)
                        horizon = -18*u.deg
                        self.lastRiset = sunrise
                        self.lastAstro = calc_riseset(now, 'sun', self.obs, 'previous', 'rising', horizon)

                    # Configure the corresponding text fields
                    self.riset.configure(
                        text=self.lastRiset.datetime.strftime("%H:%M:%S")
                    )
                    self.astro.configure(
                        text=self.lastAstro.datetime.strftime("%H:%M:%S")
                    )

        except Exception as err:
            # catchall
            g.clog.warn('AstroFrame.update: error = ' + str(err))

        # run again after 100 milli-seconds
        self.after(100, self.update)


class WinPairs(tk.Frame):
    """
    Class to define a frame of multiple window pairs,
    contained within a gridded block that can be easily position.
    """

    def __init__(self, master, xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs,
                 yss, ysmins, ysmaxs, nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xsls, xslmins, xslmaxs :
            initial X values of the leftmost columns of left-hand windows
            along with minimum and maximum values (array-like)

          xsrs, xsrmins, xsrmaxs :
            initial X values of the leftmost column of right-hand windows
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            Y dimensions of windows, unbinned pixels
            (array-like)

          xbfac :
            array of unique x-binning factors

          ybfac :
            array of unique y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.

        It is assumed that the maximum X dimension is the same for both left
        and right windows and equal to xslmax-xslmin+1.
        """
        npair = len(xsls)
        checks = (xsls, xslmins, xslmaxs, xsrs, xsrmins, xsrmaxs,
                  yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if npair != len(check):
                raise DriverError(
                    'drivers.WindowPairs.__init__:' +
                    ' conflict array lengths amonst inputs')

        super(WinPairs, self).__init__(master)

        # top part contains the binning factors and
        # the number of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0, column=1, sticky=tk.W)

        row = 1
        allowed_pairs = (1, 2, 4)
        ap = [pairnum for pairnum in allowed_pairs if pairnum <= npair]
        self.npair = ListInt(top, ap[0], ap, checker, width=2)
        if npair > 1:
            # Second row: number of windows
            tk.Label(top, text='Number of window pairs').grid(
                row=1, column=0, sticky=tk.W)
            self.npair.grid(row=row, column=1, sticky=tk.W, pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xsl').grid(row=row, column=1, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='xsr').grid(row=row, column=2, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row, column=3, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row, column=4, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row, column=5, ipady=5, sticky=tk.S)

        row += 1
        (self.label, self.xsl, self.xsr,
         self.ys, self.nx, self.ny) = [], [], [], [], [], []
        nr = 0
        for (xsl, xslmin, xslmax, xsr, xsrmin,
             xsrmax, ys, ysmin, ysmax, nx, ny) in zip(*checks):

            # create
            if npair == 1:
                self.label.append(tk.Label(bottom, text='Pair: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Pair ' + str(nr) + ': '))

            self.xsl.append(
                RangedInt(bottom, xsl, xslmin, xslmax, checker, True, width=4))
            self.xsr.append(
                RangedInt(bottom, xsr, xsrmin, xsrmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xslmax-xslmin+1, self.xbin,
                           checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1, self.ybin,
                           checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row, column=0)
            self.xsl[-1].grid(row=row, column=1)
            self.xsr[-1].grid(row=row, column=2)
            self.ys[-1].grid(row=row, column=3)
            self.nx[-1].grid(row=row, column=4)
            self.ny[-1].grid(row=row, column=5)

            row += 1
            nr += 1

        # syncing button
        self.sbutt = ActButton(bottom, 5, self.sync, text='Sync')
        self.sbutt.grid(row=row, column=0, columnspan=5, pady=10, sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the window pairs. If any problems are found, it
        flags them by changing the background colour.

        Returns (status, synced)

          status : flag for whether parameters are viable at all
          synced : flag for whether the windows are synchronised.
        """

        status = True
        synced = True

        xbin = self.xbin.value()
        ybin = self.ybin.value()
        npair = self.npair.value()

        g = get_root(self).globals
        # individual pair checks
        for xslw, xsrw, ysw, nxw, nyw in zip(self.xsl[:npair], self.xsr[:npair],
                                             self.ys[:npair], self.nx[:npair],
                                             self.ny[:npair]):
            xslw.config(bg=g.COL['main'])
            xsrw.config(bg=g.COL['main'])
            ysw.config(bg=g.COL['main'])
            nxw.config(bg=g.COL['main'])
            nyw.config(bg=g.COL['main'])
            status = status if xslw.ok() else False
            status = status if xsrw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xsl = xslw.value()
            xsr = xsrw.value()
            ys = ysw.value()
            nx = nxw.value()
            ny = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=g.COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=g.COL['error'])
                status = False

            # overlap checks
            if xsl is None or xsr is None or xsl >= xsr:
                xsrw.config(bg=g.COL['error'])
                status = False

            if xsl is None or xsr is None or nx is None or xsl + nx > xsr:
                xsrw.config(bg=g.COL['error'])
                status = False

            # Are the windows synchronised? This means that they would
            # be consistent with the pixels generated were the whole CCD
            # to be binned by the same factors. If relevant values are not
            # set, we count that as "synced" because the purpose of this is
            # to enable / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            perform_check = all([param is not None for param in (xsl, xsr, ys, nx, ny)])
            if (perform_check and
                ((xsl - 1) % xbin != 0 or (xsr - 1) % xbin != 0 or
                 (ys - 1) % ybin != 0)):
                synced = False

            # Range checks
            if xsl is None or nx is None or xsl + nx - 1 > xslw.imax:
                xslw.config(bg=g.COL['error'])
                status = False

            if xsr is None or nx is None or xsr + nx - 1 > xsrw.imax:
                xsrw.config(bg=g.COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=g.COL['error'])
                status = False

        # Pair overlap checks. Compare one pair with the next one upstream
        # (if there is one). Only bother if we have survived so far, which
        # saves a lot of checks
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:npair-1], self.ny[:npair-1]):
                ys1 = ysw1.value()
                ny1 = nyw1.value()

                n1 += 1

                ysw2 = self.ys[n1]

                ys2 = ysw2.value()

                if ys1 + ny1 > ys2:
                    ysw2.config(bg=g.COL['error'])
                    status = False

        if synced:
            self.sbutt.config(bg=g.COL['main'])
            self.sbutt.disable()
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=g.COL['warn'])

        return status

    def sync(self):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factors == 1.
        """

        # needs some mods for ultracam ??
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xsl, xsr, ys, nx, ny in self:
            if xbin > 1:
                if xsl % xbin != 1:
                    xsl = xbin*((xsl-1)//xbin)+1
                    self.xsl[n].set(xsl)
                if xsr % xbin != 1:
                    xsr = xbin*((xsr-1)//xbin)+1
                    self.xsr[n].set(xsr)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze (disable) all settings so they can't be altered
        """
        for xsl, xsr, ys, nx, ny in \
                zip(self.xsl, self.xsr,
                    self.ys, self.nx, self.ny):
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.npair.disable()
        self.xbin.disable()
        self.ybin.disable()
        self.sbutt.disable()
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings so that they can be altered
        """
        self.enable()
        self.frozen = False
        self.check()

    def disable(self, everything=False):
        """
        Disable all but possibly not binning, which is needed for FF apps

        Parameters
        ---------
        everything : bool
            disable binning as well
        """
        self.freeze()
        if not everything:
            self.xbin.enable()
            self.ybin.enable()
        self.frozen = False

    def enable(self):
        """
        Enables WinPair settings
        """
        npair = self.npair.value()
        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[:npair], self.xsl[:npair], self.xsr[:npair],
                    self.ys[:npair], self.nx[:npair], self.ny[:npair]):
            label.config(state='normal')
            xsl.enable()
            xsr.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xsl, xsr, ys, nx, ny in \
                zip(self.label[npair:], self.xsl[npair:], self.xsr[npair:],
                    self.ys[npair:], self.nx[npair:], self.ny[npair:]):
            label.config(state='disable')
            xsl.disable()
            xsr.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.npair.enable()
        self.xbin.enable()
        self.ybin.enable()
        self.sbutt.enable()

    def __iter__(self):
        """
        Generator to allow looping through through the window pairs.
        Successive calls return xsl, xsr, ys, nx, ny for each pair
        """
        n = 0
        npair = self.npair.value()
        while n < npair:
            yield (self.xsl[n].value(), self.xsr[n].value(),
                   self.ys[n].value(), self.nx[n].value(), self.ny[n].value())
            n += 1


class Windows(tk.Frame):
    """
    Class to define a frame of multiple windows as a gridded
    block that can be placed easily within a container widget.
    Also defines binning factors and the number of active windows.
    """

    def __init__(self, master, xss, xsmins, xsmaxs, yss, ysmins, ysmaxs,
                 nxs, nys, xbfac, ybfac, checker):
        """
        Arguments:

          master :
            container widget

          xss, xsmins, xsmaxs :
            initial X values of the leftmost column of window(s)
            along with minimum and maximum values (array-like)

          yss, ysmins, ysmaxs :
            initial Y values of the lowest row of the window
            along with minimum and maximum values (array-like)

          nxs :
            initial X dimensions of windows, unbinned pixels
            (array-like)

          nys :
            initial Y dimension(s) of windows, unbinned pixels
            (array-like)

          xbfac :
            set of x-binning factors

          ybfac :
            set of y-binning factors

          checker :
            checker function to provide a global check and update in response
            to any changes made to the values stored in a Window. Can be None.
        """

        nwin = len(xss)
        checks = (xss, xsmins, xsmaxs, yss, ysmins, ysmaxs, nxs, nys)
        for check in checks:
            if nwin != len(check):
                raise DriverError('drivers.Windows.__init__: ' +
                                  'conflict array lengths amonst inputs')

        tk.Frame.__init__(self, master)

        # top part contains the binning factors and the number
        # of active windows
        top = tk.Frame(self)
        top.pack(anchor=tk.W)

        tk.Label(top, text='Binning factors (X x Y): ').grid(
            row=0, column=0, sticky=tk.W)

        xyframe = tk.Frame(top)
        self.xbin = ListInt(xyframe, xbfac[0], xbfac, checker, width=2)
        self.xbin.pack(side=tk.LEFT)
        tk.Label(xyframe, text=' x ').pack(side=tk.LEFT)
        self.ybin = ListInt(xyframe, ybfac[0], ybfac, checker, width=2)
        self.ybin.pack(side=tk.LEFT)
        xyframe.grid(row=0, column=1, sticky=tk.W)

        # Second row: number of windows
        self.nwin = RangedInt(top, 1, 1, nwin, checker, False, width=2)
        row = 1
        if nwin > 1:
            tk.Label(top, text='Number of windows').grid(row=row, column=0,
                                                         sticky=tk.W)
            self.nwin.grid(row=1, column=1, sticky=tk.W, pady=2)
            row += 1

        # bottom part contains the window settings
        bottom = tk.Frame(self)
        bottom.pack(anchor=tk.W)

        # top row
        tk.Label(bottom, text='xs').grid(row=row, column=1, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='ys').grid(row=row, column=2, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='nx').grid(row=row, column=3, ipady=5, sticky=tk.S)
        tk.Label(bottom, text='ny').grid(row=row, column=4, ipady=5, sticky=tk.S)

        self.label, self.xs, self.ys, self.nx, self.ny = [], [], [], [], []
        nr = 0
        row += 1
        for xs, xsmin, xsmax, ys, ysmin, ysmax, nx, ny in zip(*checks):

            # create
            if nwin == 1:
                self.label.append(tk.Label(bottom, text='Window: '))
            else:
                self.label.append(
                    tk.Label(bottom, text='Window ' + str(nr+1) + ': '))

            self.xs.append(
                RangedInt(bottom, xs, xsmin, xsmax, checker, True, width=4))
            self.ys.append(
                RangedInt(bottom, ys, ysmin, ysmax, checker, True, width=4))
            self.nx.append(
                RangedMint(bottom, nx, 1, xsmax-xsmin+1,
                           self.xbin, checker, True, width=4))
            self.ny.append(
                RangedMint(bottom, ny, 1, ysmax-ysmin+1,
                           self.ybin, checker, True, width=4))

            # arrange
            self.label[-1].grid(row=row, column=0)
            self.xs[-1].grid(row=row, column=1)
            self.ys[-1].grid(row=row, column=2)
            self.nx[-1].grid(row=row, column=3)
            self.ny[-1].grid(row=row, column=4)

            row += 1
            nr += 1

        self.sbutt = ActButton(bottom, 5, self.sync, text='Sync')
        self.sbutt.grid(row=row, column=0, columnspan=5, pady=6, sticky=tk.W)
        self.frozen = False

    def check(self):
        """
        Checks the values of the windows. If any problems are found,
        it flags them by changing the background colour. Only active
        windows are checked.

        Returns status, flag for whether parameters are viable.
        """

        status = True
        synced = True

        xbin = self.xbin.value()
        ybin = self.ybin.value()
        nwin = self.nwin.value()

        # individual window checks
        g = get_root(self).globals
        for xsw, ysw, nxw, nyw in \
                zip(self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):

            xsw.config(bg=g.COL['main'])
            ysw.config(bg=g.COL['main'])
            nxw.config(bg=g.COL['main'])
            nyw.config(bg=g.COL['main'])
            status = status if xsw.ok() else False
            status = status if ysw.ok() else False
            status = status if nxw.ok() else False
            status = status if nyw.ok() else False
            xs = xsw.value()
            ys = ysw.value()
            nx = nxw.value()
            ny = nyw.value()

            # Are unbinned dimensions consistent with binning factors?
            if nx is None or nx % xbin != 0:
                nxw.config(bg=g.COL['error'])
                status = False

            if ny is None or ny % ybin != 0:
                nyw.config(bg=g.COL['error'])
                status = False

            # Are the windows synchronised? This means that they
            # would be consistent with the pixels generated were
            # the whole CCD to be binned by the same factors
            # If relevant values are not set, we count that as
            # "synced" because the purpose of this is to enable
            # / disable the sync button and we don't want it to be
            # enabled just because xs or ys are not set.
            if xs is not None and ys is not None and nx is not None and \
                    ny is not None and \
                    ((xs - 1) % xbin != 0 or (ys - 1) % ybin != 0):
                synced = False

            # Range checks
            if xs is None or nx is None or xs + nx - 1 > xsw.imax:
                xsw.config(bg=g.COL['error'])
                status = False

            if ys is None or ny is None or ys + ny - 1 > ysw.imax:
                ysw.config(bg=g.COL['error'])
                status = False

        # Overlap checks. Compare each window with the next one, requiring
        # no y overlap and that the second is higher than the first
        if status:
            n1 = 0
            for ysw1, nyw1 in zip(self.ys[:nwin-1], self.ny[:nwin-1]):

                ys1 = ysw1.value()
                ny1 = nyw1.value()

                n1 += 1
                ysw2 = self.ys[n1]

                ys2 = ysw2.value()

                if ys2 < ys1 + ny1:
                    ysw2.config(bg=g.COL['error'])
                    status = False

        if synced:
            self.sbutt.config(bg=g.COL['main'])
            self.sbutt.disable()
        else:
            if not self.frozen:
                self.sbutt.enable()
            self.sbutt.config(bg=g.COL['warn'])

        return status

    def sync(self, *args):
        """
        Synchronise the settings. This means that the pixel start
        values are shifted downwards so that they are synchronised
        with a full-frame binned version. This does nothing if the
        binning factor == 1
        """
        xbin = self.xbin.value()
        ybin = self.ybin.value()
        n = 0
        for xs, ys, nx, ny in self:
            if xbin > 1 and xs % xbin != 1:
                xs = xbin*((xs-1)//xbin)+1
                self.xs[n].set(xs)

            if ybin > 1 and ys % ybin != 1:
                ys = ybin*((ys-1)//ybin)+1
                self.ys[n].set(ys)

            n += 1
        self.sbutt.config(state='disable')

    def freeze(self):
        """
        Freeze all settings so they can't be altered
        """
        for xs, ys, nx, ny in \
                zip(self.xs, self.ys, self.nx, self.ny):
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()
        self.nwin.disable()
        self.xbin.disable()
        self.ybin.disable()
        self.sbutt.disable()
        self.frozen = True

    def unfreeze(self):
        """
        Unfreeze all settings
        """
        self.enable()
        self.frozen = False
        self.check()

    def enable(self):
        """
        Enables all settings
        """
        nwin = self.nwin.value()
        for label, xs, ys, nx, ny in \
                zip(self.label[:nwin], self.xs[:nwin], self.ys[:nwin],
                    self.nx[:nwin], self.ny[:nwin]):
            label.config(state='normal')
            xs.enable()
            ys.enable()
            nx.enable()
            ny.enable()

        for label, xs, ys, nx, ny in \
                zip(self.label[nwin:], self.xs[nwin:], self.ys[nwin:],
                    self.nx[nwin:], self.ny[nwin:]):
            label.config(state='disable')
            xs.disable()
            ys.disable()
            nx.disable()
            ny.disable()

        self.nwin.enable()
        self.xbin.enable()
        self.ybin.enable()
        self.sbutt.enable()

    def __iter__(self):
        """
        Generator to allow looping through through the window values.
        Successive calls return xs, ys, nx, ny for each window
        """
        n = 0
        nwin = self.nwin.value()
        while n < nwin:
            yield (self.xs[n].value(), self.ys[n].value(),
                   self.nx[n].value(), self.ny[n].value())
            n += 1