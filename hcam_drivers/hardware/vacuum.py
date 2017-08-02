# Utility to communicate with MKS PDR900 Vacuum Guage via RS232
from __future__ import absolute_import, unicode_literals, print_function, division
import serial
import time
import re

from astropy.utils.decorators import lazyproperty
from astropy.time import Time, TimeDelta
from astropy.io import ascii
from astropy import units as u

from .termserver import netdevice

DEFAULT_TIMEOUT = 5  # seconds

# MESSAGES (as strings, don't forget to format and encode)
DOWNLOAD = '@{addr:03d}DL{comm};FF'
SERIAL_NO = '@{addr:03d}SNC{comm};FF'
FIRMWARE = '@{addr:03d}FVC{comm};FF'
ADDRESS = '@{addr:03d}ADC{comm};FF'
DLOG_CTRL = '@{addr:03d}DLC{comm};FF'
DLOG_TIME = '@{addr:03d}DLT{comm};FF'
PRESSURE = '@{addr:03d}PR1{comm};FF'


class VacuumGaugeError(Exception):
    pass


class PDR900(object):

    def __init__(self, host='195.194.120.72', port=10002):
        """
        Creates a PDR900 object for communication over serial.

        Parameters
        -----------
         port : string
            port device representing the vacuum gauge
        """
        self.port = port
        self.host = host
        self.logging_start_time = None

        # connect once to find address and hard-code
        data = dict(addr=254, comm='?')
        _, addr = self._send_recv(ADDRESS, data)
        self.address = addr

    def _parse_response(self, response):
        pattern = '@(.*)ACK(.*);FF'
        result = re.match(pattern, response)
        if result is None:
            raise VacuumGaugeError('could not parse response {}'.format(
                response
            ))
        if len(result.groups()) != 2:
            raise VacuumGaugeError('unexpected result when parsing response {}'.format(
                response
            ))
        return result.groups()

    def _send_recv(self, message, data):
        msg = message.format(**data).encode()
        with netdevice(self.host, self.port, DEFAULT_TIMEOUT) as dev:
            dev.send(msg)
            dev.settimeout(DEFAULT_TIMEOUT)
            response = dev.recv(1024).decode().rstrip('\r\n')
        addr, retval = self._parse_response(response)
        return addr, retval

    @lazyproperty
    def firmware_version(self):
        data = dict(addr=self.address, comm='?')
        _, fwver = self._send_recv(FIRMWARE, data)
        return fwver

    @lazyproperty
    def serial_number(self):
        data = dict(addr=self.address, comm='?')
        _, serno = self._send_recv(SERIAL_NO, data)
        return serno

    def start_logging(self):
        data = dict(addr=self.address, comm='!START')
        addr, response = self._send_recv(DLOG_CTRL, data)
        if response != 'START':
            raise VacuumGaugeError('failed to start logging')
        self.logging_start_time = Time.now()

    def set_log_interval(self, hours, mins, secs):
        assert secs < 60, 'seconds must be less than 60'
        assert mins < 60, 'minutes must be less than 60'
        tstring = '!{:02d}:{:02d}:{:02d}'.format(hours, mins, secs)
        data = dict(addr=self.address, comm=tstring)
        addr, response = self._send_recv(DLOG_TIME, data)
        if response != tstring[1:]:
            raise VacuumGaugeError('failed to set logging time')

    def get_log_interval(self):
        data = dict(addr=self.address, comm='?')
        addr, response = self._send_recv(DLOG_TIME, data)
        try:
            h, m, s = [float(val) for val in response.split(':')]
        except:
            raise VacuumGaugeError('cannot parse log interval response: ' + response)
        return TimeDelta(3600*h + 60*m + s, format='sec')

    def get_log_data(self):
        data = dict(add=self.address, comm='?')
        addr, pdata = self._send_recv(DOWNLOAD, data)
        return ascii.read(pdata, delimiter=';')

    def get_latest(self):
        data = self.get_log_data()
        last_row = data[-1]
        h, m, s = [float(val) for val in last_row['TIME'].split(':')]
        dt = TimeDelta(3600*h + 60*m + s, format='sec')
        now = Time.now()
        age = self.logging_start_time + dt - now
        if age > 10*u.min:
            raise VacuumGaugeError('latest data is older than 10 minutes')
        return float(last_row['MB TORR'])
