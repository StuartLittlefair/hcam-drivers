# module to talk to the arduino in the thermal enclosure
from six.moves.urllib.error import URLError
from six.moves.urllib.request import urlopen
import threading

from hcam_widgets import DriverError


class GTCRackSensor(object):
    def __init__(self, address):
        self.url = 'http://{}/'.format(address)
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            try:
                resp = urlopen(self.url, timeout=5)
                try:
                    status = resp.status
                except AttributeError:
                    status = resp.getcode()
                if status != 200:
                    raise URLError('response code from rack sensor NOK')
                html = resp.read().decode()
                fields = html.split('">')
                temp = float(fields[1].split(' ')[0])
                hum = float(fields[2].split(' ')[0])
                return temp, hum
            except URLError as err:
                raise DriverError(str(err))

    @property
    def temperature(self):
        t, h = self.__call__()
        return t

    @property
    def humidity(self):
        t, h,  = self.__call__()
        return h
