# The task of the classes and functions here is to convert
# JSON encoded instrument setups into an
from __future__ import print_function, unicode_literals, absolute_import, division


def get_obsmode(setup_data):
    mode = setup_data['appdata']['app']
    if mode == 'FullFrame':
        return FullFrame(setup_data)
    elif mode == 'Windows':
        return Windows(setup_data)
    elif mode == 'Drift':
        return Drift(setup_data)
    else:
        raise ValueError('Unrecognised mode: {}'.format(mode))


class ObsMode(object):

    def __init__(self, setup_data):
        """
        The base class for all HiPERCAM modes.

        Parameters
        ----------
        setup_data : dict
            Dictionary of HiPerCAM setup data
        """
        app_data = setup_data['appdata']
        nb, ng, nr, ni, nz = app_data['multipliers']
        self.detpars = {
            'DET.BINX1': app_data['xbin'],
            'DET.BINY1': app_data['ybin'],
            'DET.CLRCCD': 'T' if app_data['clear'] else 'F',
            'DET.NCLRS': 10,
            'DET.DUMMY': 0,
            'DET.EXPLED': 'T' if app_data['led_flsh'] else 'F',
            'DET.GPS': 'T',
            'DET.INCPRSCX': 'T' if app_data['oscan'] else 'F',
            'DET.NSKIPS1': nb-1,
            'DET.NSKIPS2': ng-1,
            'DET.NSKIPS3': nr-1,
            'DET.NSKIPS4': ni-1,
            'DET.NSKIPS5': nz-1,
            'DET.SEQ.DIT': app_data['exptime']
        }

    @property
    def readmode_command(self):
        return 'setup DET.READ.CURID {}'.format(self.readoutMode)

    @property
    def setup_command(self):
        setup_string = 'setup'
        for key in self.detpars:
            setup_string += ' {} {} '.format(key, self.detpars[key])
        return setup_string


class FullFrame(ObsMode):
    def __init__(self, setup_data):
        super(FullFrame, self).__init__(setup_data)
        modes = dict(Slow=1, Medium=1, Fast=1)
        self.readoutMode = modes[setup_data['appdata']['readout']]


class Windows(ObsMode):
    def __init__(self, setup_data):
        super(Windows, self).__init__(setup_data)
        app_data = setup_data['appdata']
        win1 = {
            'DET.WIN1.NX': app_data['x1size'],
            'DET.WIN1.NY': app_data['y1size'],
            'DET.WIN1.XSE': app_data['x1start_lowerleft'] - 1,
            'DET.WIN1.XSF': app_data['x1start_lowerright'] - 1025,
            'DET.WIN1.XSG': app_data['x1start_upperright'] - 1025,
            'DET.WIN1.XSH': app_data['x1start_upperleft'] - 1,
            'DET.WIN1.YS': app_data['y1start'] - 1
        }
        self.detpars.update(win1)
        if 'x2size' in app_data:
            win2 = {
                'DET.WIN2.NX': app_data['x2size'],
                'DET.WIN2.NY': app_data['y2size'],
                'DET.WIN2.XSE': app_data['x2start_lowerleft'] - 1,
                'DET.WIN2.XSF': app_data['x2start_lowerright'] - 1025,
                'DET.WIN2.XSG': app_data['x2start_upperright'] - 1025,
                'DET.WIN2.XSH': app_data['x2start_upperleft'] - 1,
                'DET.WIN2.YS': app_data['y2start'] - 1
            }
            self.detpars.update(win2)
        self.speed = app_data['readout']

    @property
    def readoutMode(self):
        if 'DET.WIN2.NX' in self.detpars:
            modes = dict(Slow=3, Medium=3, Fast=3)
        else:
            modes = dict(Slow=2, Medium=2, Fast=2)
        return modes[self.speed]


class Drift(ObsMode):
    def __init__(self, setup_data):
        super(Drift, self).__init__(setup_data)
        app_data = setup_data['appdata']
        win1 = {
            'DET.WIN1.NX': app_data['x1size'],
            'DET.WIN1.NY': app_data['y1size'],
            'DET.WIN1.YS': app_data['y1start'] - 1,
            'DET.WIN1.XSE': app_data['x1start_left'] - 1,
            'DET.WIN1.XSF': app_data['x1start_right'] - 1025,
            'DET.WIN1.XSH': app_data['x1start_left'] - 1,
            'DET.WIN1.XSG': app_data['x1start_right'] - 1025
        }
        self.detpars.update(win1)
        self.detpars['DET.WIN1.NW'] = self.num_stacked
        self.detpars['DET.WIN1.PSH'] = self.pipe_shift

    @property
    def num_stacked(self):
        """
        Number of windows stacked in frame transfer area
        """
        ny = self.detpars['DET.WIN1.NY']
        return int((self.nrows/ny + 1) / 2)

    @property
    def pipe_shift(self):
        """
        Extra shift to add to some windows to ensure uniform exposure time.

        Returned in units of vertical clocks. Should be multiplied by the
        vclock time to obtain pipe_shift in seconds.
        """
        ny = self.detpars['DET.WIN1.NY']
        return (self.nrows - (2*self.num_stacked - 1)*ny)
