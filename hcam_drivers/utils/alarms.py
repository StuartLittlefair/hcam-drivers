# module to open alarm widget which appears and flashes and plays noise
from __future__ import print_function, unicode_literals, absolute_import, division
import six
import subprocess
import sys
import pkg_resources
from hcam_widgets.tkutils import addStyle, get_root

if not six.PY3:
    import Tkinter as tk
else:
    import tkinter as tk

alarm_file = pkg_resources.resource_filename(
    'hcam_drivers', 'data/phat_alarm.mp3'
)
alarm_cmd = '{} {}'.format(
    'afplay' if sys.platform == 'darwin' else 'aplay',
    alarm_file
)


class AlarmDialog(tk.Toplevel):
    """
    A widget that appears when an alarm is raised.

    A simple dialog widget that displays an alarm message.
    It also plays an alarm sound, and allows you to acknowledge
    the alarm, which silences the sound and destroys the widget.

    Arguments
    ----------
    widget : `hcam_drivers.hardware.HardwareDisplayWidget`
        calling hardware widget
    msg : string
        the alarm message
    play_sound : bool
        play alarm sound y/n?
    title : string, optional
        title for widget
    """
    def __init__(self, widget, msg, play_sound=True, title='Alarm'):
        parent = widget.parent
        tk.Toplevel.__init__(self, parent)
        self.transient(parent)
        self.title(title)
        self.parent = parent
        self.widget = widget
        self.result = None
        body = tk.Frame(self)
        tk.Label(body, text=msg).pack()
        body.pack(padx=5, pady=5)
        self.buttonbox()

        self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.ack_and_teardown)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))
        self.initial_focus.focus_set()
        if play_sound:
            self.alarm_proc = subprocess.Popen(alarm_cmd, shell=True)
        else:
            self.alarm_proc = None
        addStyle(self)

    def buttonbox(self):
        # add standard button box. override if you don't want the
        # standard buttons
        box = tk.Frame(self)
        g = get_root(self).globals
        w = tk.Button(box, text="OK", width=10, bg=g.COL['start'],
                      command=self.cancel, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="ACK", width=10, bg=g.COL['warn'],
                      command=self.ack, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.cancel)
        box.pack()

    #
    # standard button semantics
    def ack(self, event=None):
        # just stop the noise
        if self.alarm_proc:
            self.alarm_proc.kill()
        self.widget.acknowledge_alarm()

    def teardown(self):
        self.withdraw()
        self.update_idletasks()
        self.parent.focus_set()
        self.destroy()

    def cancel(self, event=None):
        # cancel alarm
        if self.alarm_proc:
            self.alarm_proc.kill()
        self.widget.cancel_alarm()
        self.teardown()

    def ack_and_teardown(self):
        self.ack()
        self.teardown()
