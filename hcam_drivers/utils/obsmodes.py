# The task of the classes and functions here is to convert
# JSON encoded instrument setups into an
from __future__ import print_function, unicode_literals, absolute_import, division
from collections import OrderedDict


def get_obsmode(setup_data):
    mode = setup_data['appdata']['app']
    if mode == 'FullFrame':
        return FullFrame(setup_data)
    elif mode == 'Windows':
        return Windows(setup_data)
    elif mode == 'Drift':
        return Drift(setup_data)
    elif mode == 'Idle':
        return Idle()
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
        nu, ng, nr, ni, nz = app_data['multipliers']
        dummy = app_data.get('dummy_out', 0)  # works even if dummy not set in app, default 0
        fastclk = app_data.get('fast_clks', 0)
        oscany = app_data.get('oscany', 0)

        clockfile = 'hipercam.bclk'
        if not dummy:
            clockfile = 'hipercam_se.bclk'
        elif fastclk:
            clockfile = 'hipercam_fastclk.bclk'

        self.finite = app_data['numexp']
        self.detpars = {
            'DET.SPEED': 0 if app_data['readout'] == 'Slow' else 1,
            'DET.BINX1': app_data['xbin'],
            'DET.BINY1': app_data['ybin'],
            'DET.CLRCCD': 'T' if app_data['clear'] else 'F',
            'DET.NCLRS': 5,
            'DET.DUMMY': dummy,
            'DET.FASTCLK': fastclk,
            'DET.EXPLED': 'T' if app_data['led_flsh'] else 'F',
            'DET.GPS': 'T',
            'DET.INCPRSCX': 'T' if app_data['oscan'] else 'F',
            'DET.INCOVSCY': 'T' if oscany else 'F',
            'DET.NSKIPS1': nu-1,
            'DET.NSKIPS2': ng-1,
            'DET.NSKIPS3': nr-1,
            'DET.NSKIPS4': ni-1,
            'DET.NSKIPS5': nz-1,
            'DET.SEQ.CLKFILE': clockfile,
            'DET.SEQ1.DIT': app_data['exptime'],
            'DET.TDELAY.GUI': 1000*app_data['dwell']
        }

        # parameters for user-defined headers
        user_data = setup_data.get('user', {})
        userpars = []
        userpars.extend([
            ('OBSERVER', user_data.get('Observers', '')),
            ('OBJECT', user_data.get('target', '')),
            ('RUNCOM', user_data.get('comment', '')),
            ('IMAGETYP', user_data.get('flags', '')),
            ('FILTERS', user_data.get('filters', '')),
            ('PROGRM', user_data.get('ID', '')),
            ('PI', user_data.get('PI', ''))
        ])

        # data from TCS
        tcs_data = setup_data.get('tcs', {})
        userpars.extend([
            ('TELESCOP', tcs_data.get('tel', 'WHT')),
            ('RA', tcs_data.get('RA', '00:00:00.00')),
            ('DEC', tcs_data.get('DEC', '+00:00:00.0')),
            ('ALTITUDE', tcs_data.get('alt', -99)),
            ('AZIMUTH', tcs_data.get('az', -99)),
            ('AIRMASS', tcs_data.get('secz', -99)),
            ('PA', tcs_data.get('pa', -99)),
            ('FOCUS', tcs_data.get('foc', -99)),
            ('MOONDIST', tcs_data.get('mdist', -99))
        ])

        # data from h/w monitoring processes
        hw_data = setup_data.get('hardware', {})
        userpars.extend([
            ('CCD1TEMP', hw_data.get('ccd1temp', -99)),
            ('CCD2TEMP', hw_data.get('ccd2temp', -99)),
            ('CCD3TEMP', hw_data.get('ccd3temp', -99)),
            ('CCD4TEMP', hw_data.get('ccd4temp', -99)),
            ('CCD5TEMP', hw_data.get('ccd5temp', -99)),
            ('CCD1VAC', hw_data.get('ccd1vac', -99)),
            ('CCD2VAC', hw_data.get('ccd2vac', -99)),
            ('CCD3VAC', hw_data.get('ccd3vac', -99)),
            ('CCD4VAC', hw_data.get('ccd4vac', -99)),
            ('CCD5VAC', hw_data.get('ccd5vac', -99)),
            ('CCD1FLOW', hw_data.get('ccd1flow', -99)),
            ('CCD2FLOW', hw_data.get('ccd2flow', -99)),
            ('CCD3FLOW', hw_data.get('ccd3flow', -99)),
            ('CCD4FLOW', hw_data.get('ccd4flow', -99)),
            ('CCD5FLOW', hw_data.get('ccd5flow', -99)),
            ('FPSLIDE', hw_data.get('fpslide', -99))
        ])
        self.userpars = OrderedDict(userpars)

    @property
    def readmode_command(self):
        return 'setup DET.READ.CURID {}'.format(self.readoutMode)

    @property
    def setup_command(self):
        setup_string = 'setup'

        for key in self.detpars:
            setup_string += ' {} {} '.format(key, self.detpars[key])

        # userpars first, because order dictates appearance in FITS header
        for key in self.userpars:
            if self.userpars[key] != '':
                value = self.userpars[key]
                # add quotes to strings with spaces
                try:
                    if ' ' in value:
                        value = '"' + value + '"'
                except:
                    pass
                setup_string += ' {} {} '.format(key, value)

        if self.finite:
            setup_string += ' DET.FRAM2.BREAK {} '.format(self.finite)

        return setup_string


class FullFrame(ObsMode):
    def __init__(self, setup_data):
        super(FullFrame, self).__init__(setup_data)
        self.readoutMode = 1


class Idle(ObsMode):
    """
    An idle mode to keep clearing the chip and stop taking GPS timestamps.
    """
    def __init__(self):
        app_data = {
            'xbin': 1,
            'ybin': 1,
            'clear': True,
            'readout': 'Slow',
            'led_flsh': False,
            'oscan': False,
            'dummy': 1,
            'numexp': 0,
            'oscany': False,
            'multipliers': (1, 1, 1, 1, 1),
            'exptime': 10,
            'dwell': 10
        }
        setup_data = {'appdata': app_data}
        super(Idle, self).__init__(setup_data)
        self.detpars['DET.GPS'] = 'F'
        self.readoutMode = 1  # FF, Slow


class Windows(ObsMode):
    def __init__(self, setup_data):
        super(Windows, self).__init__(setup_data)
        app_data = setup_data['appdata']
        win1 = {
            'DET.WIN1.NX': app_data['x1size'],
            'DET.WIN1.NY': app_data['y1size'],
            'DET.WIN1.XSE': app_data['x1start_lowerleft'] - 1,
            'DET.WIN1.XSF': 2049 - app_data['x1start_lowerright'] - app_data['x1size'],
            'DET.WIN1.XSG': 2049 - app_data['x1start_upperright'] - app_data['x1size'],
            'DET.WIN1.XSH': app_data['x1start_upperleft'] - 1,
            'DET.WIN1.YS': app_data['y1start'] - 1,
            'DET.WIN1.YS.GUI': app_data['y1start'],
            'DET.WIN1.XSLL': app_data['x1start_lowerleft'],
            'DET.WIN1.XSLR': app_data['x1start_lowerright'],
            'DET.WIN1.XSUL': app_data['x1start_upperleft'],
            'DET.WIN1.XSUR': app_data['x1start_upperright']
        }
        self.detpars.update(win1)
        if 'x2size' in app_data:
            win2 = {
                'DET.WIN2.NX': app_data['x2size'],
                'DET.WIN2.NY': app_data['y2size'],
                'DET.WIN2.XSE': app_data['x2start_lowerleft'] - 1,
                'DET.WIN2.XSF': 2049 - app_data['x2start_lowerright'] - app_data['x2size'],
                'DET.WIN2.XSG': 2049 - app_data['x2start_upperright'] - app_data['x2size'],
                'DET.WIN2.XSH': app_data['x2start_upperleft'] - 1,
                'DET.WIN2.YS': app_data['y2start'] - 1,
                'DET.WIN2.YS.GUI': app_data['y2start'],
                'DET.WIN2.XSLL': app_data['x2start_lowerleft'],
                'DET.WIN2.XSLR': app_data['x2start_lowerright'],
                'DET.WIN2.XSUL': app_data['x2start_upperleft'],
                'DET.WIN2.XSUR': app_data['x2start_upperright']
            }
            self.detpars.update(win2)

    @property
    def readoutMode(self):
        if 'DET.WIN2.NX' in self.detpars:
            mode = 3
        else:
            mode = 2
        return mode


class Drift(ObsMode):
    def __init__(self, setup_data):
        super(Drift, self).__init__(setup_data)
        app_data = setup_data['appdata']
        win1 = {
            'DET.DRWIN.NX': app_data['x1size'],
            'DET.DRWIN.NY': app_data['y1size'],
            'DET.DRWIN.YS': app_data['y1start'] - 1,
            'DET.DRWIN.YS.GUI': app_data['y1start'],
            'DET.DRWIN.XSE': app_data['x1start_left'] - 1,
            'DET.DRWIN.XSF': 2049 - app_data['x1start_right'] - app_data['x1size'],
            'DET.DRWIN.XSH': app_data['x1start_left'] - 1,
            'DET.DRWIN.XSG': 2049 - app_data['x1start_right'] - app_data['x1size'],
            'DET.DRWIN.XSL': app_data['x1start_left'],
            'DET.DRWIN.XSR': app_data['x1start_right'],
        }
        self.detpars.update(win1)
        self.nrows = 520  # number of rows in storage area
        self.readoutMode = 4

    @property
    def num_stacked(self):
        """
        Number of windows stacked in frame transfer area
        """
        ny = self.detpars['DET.DRWIN.NY']
        return int((self.nrows/ny + 1) / 2)

    @property
    def pipe_shift(self):
        """
        Extra shift to add to some windows to ensure uniform exposure time.

        Returned in units of vertical clocks. Should be multiplied by the
        vclock time to obtain pipe_shift in seconds.
        """
        ny = self.detpars['DET.DRWIN.NY']
        return (self.nrows - (2*self.num_stacked - 1)*ny)
