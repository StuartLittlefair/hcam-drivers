# Utility to query and set temps via Ethernet on Meerstetter
from __future__ import absolute_import, unicode_literals, print_function, division
import socket
import random
import six
import struct
from contextlib import contextmanager

from astropy import units as u


DEFAULT_TIMEOUT = 2


def hex_to_int(hexstring):
    return int(hexstring, 16)


def hex_to_float32(hexstring):
    if six.PY2:
        byteval = hexstring.decode('hex')
    else:
        byteval = bytes.fromhex(hexstring)
    return struct.unpack(str('!f'), byteval)[0]


def float32_to_hex(f):
    return format(struct.unpack('<I', struct.pack('<f', f))[0], 'X')


class CRCCalculator(object):
    def __init__(self):
        self.polynomial = 0x1021
        self.preset = 0
        self._lut = [self._calc_initial(i) for i in range(256)]

    def _calc_initial(self, c):
        crc = 0
        c = c << 8
        for j in range(8):
            if (crc ^ c) & 0x8000:
                crc = (crc << 1) ^ self.polynomial
            else:
                crc = crc << 1
            c = c << 1
        return crc

    def _update_crc(self, crc, c):
        cc = 0xff & c

        tmp = (crc >> 8) ^ cc
        crc = (crc << 8) ^ self._lut[tmp & 0xff]
        crc = crc & 0xffff
        return crc

    def __call__(self, msg):
        crc = self.preset
        for c in msg:
            crc = self._update_crc(crc, ord(c))
        return format(crc, '0>4X')


@contextmanager
def socketcontext(addr, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(DEFAULT_TIMEOUT)
        s.connect((addr, port))
        yield s
    finally:
        s.close()


class MeerstetterTEC1090(object):
    """
    Class to use TCP/IP to communicate with TEC-1090 controllers
    mounted in LTR-1200. Communication protocol is MeCom.

    See MeCom protocol spec document 5117B and TEC protocol document
    5136 for details.
    """
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.seq_no = random.randint(1, 1000)
        self.crc_calc = CRCCalculator()
        self.tec_power_limit = 190 * u.W

    def _assemble_frame(self, address, payload):
        """
        Assemble the frame of data to send.

        Transmissions are sent in blocks of data known as frames. Each frame has
        several fields:

        1: Control (source); ASCII Char; 1 bytes
        2: Address; UINT8; 2 bytes
        3: Sequence No; UINT16; 4 bytes
        4: Payload; N bytes
        5: Checksum, 4 bytes
        6: End of Frame, 1 byte <CR>
        """
        cs = '#'
        addr = format(address, '0>2X')
        seq = format(self.seq_no, '0>4X')
        self.seq_no += 1
        msg = cs + addr + seq + payload
        eof = '\r'
        return msg + self.crc_calc(msg) + eof

    def _send_frame(self, frame_msg):
        with socketcontext(self.address, self.port) as s:
            welcome = s.recv(1024)
            if 'Welcome' not in welcome.decode():
                raise IOError('did not receive welcome message from meerstetter')
            s.send(frame_msg.encode())
            ret_msg = s.recv(1024)
        ret_msg = ret_msg.decode().strip()
        self._check_response(frame_msg, ret_msg)
        return self._strip_response(ret_msg)

    def _check_response(self, frame_msg, ret_msg):
        if ret_msg[0] == '!' and frame_msg[1:7] == ret_msg[1:7]:
            # a valid response, and same seq no. so far so good
            crc_back = ret_msg[-4:]
            package_in = ret_msg[:-4]
            if self.crc_calc(package_in) != crc_back:
                raise IOError('checksum of return message not OK:\nOut: {}\nBack: {}'.format(
                                frame_msg, ret_msg
                              ))
        else:
            raise IOError('response not from device, or sequence number mismatch:\nOut: {}\nBack: {}'.format(
                            frame_msg, ret_msg
                          ))

    def _strip_response(self, ret_msg):
        return ret_msg[7:-4]

    def get_param(self, address, param_no, instance, param_type='float'):
        payload = '?VR{param_no:0>4X}{instance:0>2X}'.format(
            param_no=param_no, instance=instance
        )
        frame_msg = self._assemble_frame(address, payload)
        encoded_param_val = self._send_frame(frame_msg)
        if encoded_param_val == '+05':
            raise IOError('param {} not available'.format(param_no))

        if param_type == 'float':
            return hex_to_float32(encoded_param_val)
        else:
            return hex_to_int(encoded_param_val)

    def get_ccd_temp(self, address):
        param_no = 1000
        return self.get_param(address, param_no, 1)*u.Celsius

    def get_heatsink_temp(self, address):
        param_no = 1001
        return self.get_param(address, param_no, 1)*u.Celsius

    def get_power(self, address):
        current = self.get_param(address, 1020, 1)
        voltage = self.get_param(address, 1021, 1)
        return current*voltage*u.W
