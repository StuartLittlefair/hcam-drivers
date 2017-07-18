# miscellaneous useful tools
from __future__ import print_function, unicode_literals, absolute_import, division
import json
from six.moves import urllib
import six
if not six.PY3:
    import tkFileDialog as filedialog
else:
    from tkinter import filedialog
import threading
import sys
import traceback
import os
import re

from . import DriverError


class ReadServer(object):
    """
    Class to field the json responses sent back from the ULTRACAM servers

    Set the following attributes:

     root    : the decoded json response
     ok      : whether response is OK or not (True/False)
     err     : message if ok == False
     state   : state of the camera. Possibilties are:
               'IDLE', 'BUSY', 'ERROR', 'ABORT', 'UNKNOWN'
     run     : current or last run number
    """
    def __init__(self, resp, status_msg=False):
        """
        Parameters
        ----------
        resp : bytes
            response from server
        status_msg : bool (default True)
            Set True if the response should contain status info
        """
        # Store the entire response
        try:
            self.root = json.loads(resp.decode())
            self.ok = True
        except Exception:
            self.ok = False
            self.err = 'Could not parse JSON response'
            self.state = None
            self.root = dict()
            return

        # Work out whether it was happy
        if 'RETCODE' not in self.root:
            self.ok = False
            self.err = 'Could not identify status'
            self.state = None
            return
        else:
            self.ok = True if self.root['RETCODE'] == "OK" else False

        if not status_msg:
            self.state = None
            self.run = 0
            self.err = ''
            self.msg = self.root['MESSAGEBUFFER']
            return

        # Determine state of the camera
        sfind = self.root['system.subStateName']
        if sfind is 'ERR':
            self.ok = False
            self.err = 'Could not identify state'
            self.state = None
            self.root = dict()
            return
        else:
            self.ok = True
            self.err = ''
            self.state = self.root['system.subStateName']

        # Find current run number (set it to 0 if we fail)
        newDataFileName = self.root["exposure.newDataFileName"]
        exposure_state = self.root["exposure.expStatusName"]
        pattern = '\D*(\d*).*.fits'
        try:
            run_number = int(re.match(pattern, newDataFileName).group(1))
            if exposure_state == "success":
                self.run = run_number
            elif exposure_state == "aborted":
                # We use abort instead of end. Don't know why
                self.run = run_number
            elif exposure_state == "integrating":
                self.run = run_number + 1
            else:
                raise ValueError("unknown exposure state {}".format(
                    exposure_state
                ))
        except (ValueError, IndexError, AttributeError):
            self.run = 0

    def resp(self):
        return json.dumps(self.root)


def overlap(xl1, yl1, nx1, ny1, xl2, yl2, nx2, ny2):
    """
    Determines whether two windows overlap
    """
    return (xl2 < xl1+nx1 and xl2+nx2 > xl1 and
            yl2 < yl1+ny1 and yl2+ny2 > yl1)


def saveJSON(g, data, backup=False):
    """
    Saves the current setup to disk.

    g : hcam_drivers.globals.Container
    Container with globals

    data : dict
    The current setup in JSON compatible dictionary format.

    backup : bool
    If we are saving a backup on close, don't prompt for filename
    """
    if not backup:
        fname = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('json files', '.json'), ],
            initialdir=g.cpars['app_directory']
            )
    else:
        fname = os.path.join(os.path.expanduser('~/.hdriver'), 'app.json')

    if not fname:
        g.clog.warn('Aborted save to disk')
        return False

    with open(fname, 'w') as of:
        of.write(
            json.dumps(data, sort_keys=True, indent=4,
                       separators=(',', ': '))
        )
    g.clog.info('Saved setup to' + fname)
    return True


def postJSON(g, data):
    """
    Posts the current setup to the camera and data servers.

    g : hcam_drivers.globals.Container
    Container with globals

    data : dict
    The current setup in JSON compatible dictionary format.
    """
    g.clog.debug('Entering postJSON')

    # encode data as json
    json_data = json.dumps(data).encode('utf-8')

    # Send the xml to the server
    url = g.cpars['hipercam_server'] + g.SERVER_POST_PATH
    g.clog.debug('Server URL = ' + url)

    opener = urllib.request.build_opener()
    g.clog.debug('content length = ' + str(len(json_data)))
    req = urllib.request.Request(url, data=json_data, headers={'Content-type': 'application/json'})
    response = opener.open(req, timeout=5)
    csr = ReadServer(response.read(), status_msg=False)
    g.rlog.warn(csr.resp())
    if not csr.ok:
        g.clog.warn('Server response was not OK')
        return False

    g.clog.debug('Leaving postJSON')
    return True


def createJSON(g):
    """
    Create JSON compatible dictionary from current settings

    Parameters
    ----------
    g :  hcam_drivers.globals.Container
    Container with globals
    """
    data = dict()
    data['appdata'] = g.ipars.dumpJSON()
    data['user'] = g.rpars.dumpJSON()
    return data


def execCommand(g, command, timeout=10):
    """
    Executes a command by sending it to the rack server

    Arguments:
      g : hcam_drivers.globals.Container
        the Container object of application globals
      command : (string)
           the command (see below)

    Possible commands are:

      start   : starts a run
      stop    : stops a run
      abort   : aborts a run
      online  : bring ESO control server online and power up hardware
      off     : put ESO control server in idle state and power down
      standby : server can communicate, but child processes disabled
      reset   : resets the NGC controller front end

    Returns True/False according to whether the command
    succeeded or not.
    """
    if not g.cpars['hcam_server_on']:
        g.clog.warn('execCommand: servers are not active')
        return False

    try:
        url = g.cpars['hipercam_server'] + command
        g.clog.info('execCommand, command = "' + command + '"')
        response = urllib.request.urlopen(url, timeout=timeout)
        rs = ReadServer(response.read(), status_msg=False)

        g.rlog.info('Server response =\n' + rs.resp())
        if rs.ok:
            g.clog.info('Response from server was OK')
            return True
        else:
            g.clog.warn('Response from server was not OK')
            g.clog.warn('Reason: ' + rs.err)
            return False
    except urllib.error.URLError as err:
        g.clog.warn('execCommand failed')
        g.clog.warn(str(err))

    return False


def isRunActive(g):
    """
    Polls the data server to see if a run is active
    """
    if g.cpars['hcam_server_on']:
        url = g.cpars['hipercam_server'] + 'summary'
        response = urllib.request.urlopen(url, timeout=2)
        rs = ReadServer(response.read(), status_msg=True)
        if not rs.ok:
            raise DriverError('isRunActive error: ' + str(rs.err))
        if rs.state == 'idle':
            return False
        elif rs.state == 'active':
            return True
        else:
            raise DriverError('isRunActive error, state = ' + rs.state)
    else:
        raise DriverError('isRunActive error: servers are not active')


def getFrameNumber(g):
    """
    Polls the data server to find the current frame number.

    Throws an exceotion if it cannot determine it.
    """
    if not g.cpars['hcam_server_on']:
        raise DriverError('getRunNumber error: servers are not active')
    url = g.cpars['hipercam_server'] + 'status/DET.FRAM2.NO'
    response = urllib.request.urlopen(url)
    rs = ReadServer(response.read(), status_msg=False)
    try:
        msg = rs.msg
    except:
        raise DriverError('getFrameNumber error: no message found')
    try:
        frame_no = int(msg.split()[1])
    except:
        raise DriverError('getFrameNumber error: invalid msg ' + msg)
    return frame_no


def getRunNumber(g):
    """
    Polls the data server to find the current run number. Throws
    exceptions if it can't determine it.
    """

    if not g.cpars['hcam_server_on']:
        raise DriverError('getRunNumber error: servers are not active')
    url = g.cpars['hipercam_server'] + 'summary'
    response = urllib.request.urlopen(url)
    rs = ReadServer(response.read(), status_msg=True)
    if rs.ok:
        return rs.run
    else:
        raise DriverError('getRunNumber error: ' + str(rs.err))


def checkSimbad(g, target, maxobj=5, timeout=5):
    """
    Sends off a request to Simbad to check whether a target is recognised.
    Returns with a list of results, or raises an exception if it times out

    TODO: fix and make python2/3 compatible
    """
    url = 'http://simbad.u-strasbg.fr/simbad/sim-script'
    q = 'set limit ' + str(maxobj) + \
        '\nformat object form1 "Target: %IDLIST(1) | %COO(A D;ICRS)"\nquery ' \
        + target
    query = urllib.parse.urlencode({'submit': 'submit script', 'script': q})
    resp = urllib.request.urlopen(url, query.encode(), timeout)
    data = False
    error = False
    results = []
    for line in resp:
        line = line.decode()
        if line.startswith('::data::'):
            data = True
        if line.startswith('::error::'):
            error = True
        if data and line.startswith('Target:'):
            name, coords = line[7:].split(' | ')
            results.append(
                {'Name': name.strip(), 'Position': coords.strip(),
                 'Frame': 'ICRS'})
    resp.close()

    if error and len(results):
        g.clog.warn('drivers.check: Simbad: there appear to be some ' +
                    'results but an error was unexpectedly raised.')
    return results


class FifoThread(threading.Thread):
    """
    Adds a fifo Queue to a thread in order to store up disasters which are
    added to the fifo for later retrieval. This is to get around the problem
    that otherwise exceptions thrown from withins threaded operations are
    lost.
    """
    def __init__(self, target, fifo, args=()):
        super(FifoThread, self).__init__(target=target, args=args)
        self.fifo = fifo

    def run(self):
        """
        Version of run that traps Exceptions and stores
        them in the fifo
        """
        try:
            threading.Thread.run(self)
        except Exception:
            t, v, tb = sys.exc_info()
            error = traceback.format_exception_only(t, v)[0][:-1]
            tback = 'Traceback (most recent call last):\n' + \
                    ''.join(traceback.format_tb(tb))
            self.fifo.put((error, tback))
