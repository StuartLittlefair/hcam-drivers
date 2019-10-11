# Utility to query and set temp, and start circulation on Huber Unichiller 025-MPC+
from __future__ import absolute_import, unicode_literals, print_function, division
import time
import socket
import threading
import six


QUERY_DEV = '[M01V07'
QUERY_STATUS = '[M01G0D******'
STATE_CONTROL = '[M01G0D{}*****'
TEMP_SET = '[M01G0D**{}'
DEFAULT_TIMEOUT = 2

# rename socket.error
if six.PY2:
    ConnectionRefusedError = socket.error


def hex_to_float(hexstring):
    """
    The chiller encodes floats using the following hex convevntion.

    1. convert hex to int
    2. if int val > 32767, it's a negative number, subtract 65536
    3. divide by temp resolution (100)
    """
    val = int(hexstring, 16)
    if val > 32767:
        val -= 65536
    return val/100


def float_to_hex(float):
    # reverse of above
    intval = int(float*100)
    if intval <= 0:
        intval += 65536
    return '{:0>4X}'.format(intval)[-4:]


class UnichillerException(Exception):
    pass


class UnichillerMPC(object):
    """
    Class to use serial-over-ethernet to communicate with a 025-MPC
    Unichiller from Huber.

    See LAI protocol spec document for details.
    """
    def __init__(self, host, port):
        self.host = host
        self.port = port

        # thread lock for threadsafe operations
        self._lock = threading.Lock()
        # open connection on object creation
        try:
            self.connect()
        except ConnectionRefusedError:
            self.sock = None

    def __del__(self):
        # must close connection on object deletion
        self.close()

    def connect(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        s.settimeout(5)
        self.sock = s

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None

    def _checksum(self, msg):
        """
        Add a checksum to message.

        The checksum is a single byte (2 hex characters) sum of all the hex
        values in the message.

        Parameters
        ----------
        msg : string, bytes
            the message to calculate checksum of
        """
        return '{:>02X}'.format(sum(bytearray(msg, 'ascii')))[-2:]

    def _send_recv(self, msg):
        # try and connect if we are not already
        if self.sock is None:
            try:
                self.connect()
            except ConnectionRefusedError:
                raise UnichillerException('not connected')

        msg += self._checksum(msg) + '\r'
        with self._lock:
            self.sock.send(msg.encode())
            response = self.sock.recv(1024).decode().rstrip('\r')
        self._check_response(msg, response)
        return response

    def _check_response(self, msg, response):
        if response[0:4] == '[S01':
            # a valid response so far so good
            cs = response[-2:]
            package = response[:-2]
            if self._checksum(package) != cs:
                raise IOError('checksum of return message not OK:\nOut: {}\nBack: {}'.format(
                                msg, response
                              ))
        else:
            raise IOError('response not from device, or malformed:\nOut: {}\nBack: {}'.format(
                            msg, response
                          ))

    def get_status(self):
        response = self._send_recv(QUERY_STATUS)
        body = response[7:-2]
        status = dict()
        op_status = body[0]
        status['mode'] = {
            'C': 'pump on',
            'I': 'pump on, cooling on',
            'O': 'control off'
        }[op_status]
        alarm_status = body[1]
        status['alarms'] = True if alarm_status == '1' else False
        status['setpoint'] = hex_to_float(body[2:6])
        status['chiller_temp'] = hex_to_float(body[6:10])
        return status

    @property
    def temperature(self):
        status = self.get_status()
        return status['chiller_temp']

    @temperature.setter
    def temperature(self, target):
        target_hex = float_to_hex(target)
        msg = TEMP_SET.format(target_hex)
        self._send_recv(msg)

    def pump_on(self):
        msg = STATE_CONTROL.format('C')
        self._send_recv(msg)
        time.sleep(2)
        msg = STATE_CONTROL.format('I')
        self._send_recv(msg)

    def pump_off(self):
        msg = STATE_CONTROL.format('O')
        self._send_recv(msg)
