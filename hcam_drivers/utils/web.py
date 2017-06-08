# Some utility tools to handle rising and setting etc.
from __future__ import print_function, unicode_literals, absolute_import, division
import traceback
import struct

import numpy as np
import yaml
from tornado.web import RequestHandler, HTTPError
from tornado.escape import json_encode
from astropy.io import fits
from astropy.utils.decorators import lazyproperty

MSG_TEMPLATE = "MESSAGEBUFFER: {}\nRETCODE: {}"


class HServerException(HTTPError):
    pass


class BaseHandler(RequestHandler):
    """
    Abstract class for request handling
    """
    def initialize(self, db):
        self.db = db

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        resp = MSG_TEMPLATE.format(self._reason, 'NOK')
        resp_dict = yaml.load(resp)
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            lines = []
            for line in traceback.format_exception(*kwargs["exc_info"]):
                lines.append(line)
            resp_dict['traceback'] = lines
        self.finish(json_encode(resp_dict))


class FastFITSPipe:
    def __init__(self, fileobj):
        """
        Simple class to quickly read raw frame bytes from HiPERCAM FITS cube.

        For example::

            >> fileobj = open('example.fits', 'rb')
            >> ffp = FastFITSPipe(fileobj)
            >> ffp.seek_frame(100)
            >> hdu_data = ffp.read_frame_bytes()

        Parameters
        -----------
        fileobj : file-like object
            the file-like object representing a FITS file, readonly
        """
        self._fileobj = fileobj
        self.header_bytesize = 80*64*36  # 64 blocks of 36 with 80 chars
        self.dtype = np.dtype('int16')

    @lazyproperty
    def hdr(self):
        self._fileobj.seek(0)
        return fits.Header.fromfile(self._fileobj)

    #  TODO: need a robust way of finding this for all applications
    @lazyproperty
    def framesize(self):
        size = self.hdr['ESO DET ACQ1 WIN NX'] * self.hdr['ESO DET ACQ1 WIN NY']
        bitpix = self.hdr['BITPIX']
        size = abs(bitpix) * size // 8
        return size

    #  TODO: need a robust way of finding this for all applications
    @lazyproperty
    def output_shape(self):
        naxis = self.hdr.get('NAXIS', 0)
        dims = []
        if naxis > 0:
            # loop over all but leading axis (which indexes frame)
            for idx in range(1, naxis):
                dims.append(self.hdr['NAXIS' + str(idx)])
        return tuple(dims)

    def seek_frame(self, frame_number):
        """
        Try and find the start of a given frame

        Raises exception if frame not written yet
        """
        self._fileobj.seek(self.header_bytesize + self.framesize*(frame_number-1))

    def read_frame_bytes(self):
        start_pos = self._fileobj.tell()
        raw_bytes = self._fileobj.read(self.framesize)
        if len(raw_bytes) != self.framesize:
            # go back to start position
            self._fileobj.seek(start_pos)
            raise EOFError('frame not written yet')
        return raw_bytes


def raw_bytes_to_numpy(raw_data, bscale=1, bzero=32768, dtype='int16'):
    """
    Convert output from FastFITSPipe to numpy array

    For example::

        >> raw_data = ffp.read_frame_bytes()
        >> data = raw_bytes_to_numpy(raw_data)
        >> data = data.reshape(ffp.output_shape)

    Parameters
    -----------
    raw_data : bytes
        bytes returned from FastFITSPipe
    bscale : int, default = 1
        scaling to apply to raw data.
        FITS cannot stored unsigned 16-bit integers, so
        data is usually stored as signed 16-bit and then scaled
    bzero : int, default = 32768
        offset to apply to raw data
    dtype : string, default='int16'
        data type used to store data
    """
    data = np.fromstring(raw_data, np.dtype(dtype))
    data.dtype = data.dtype.newbyteorder('>')
    np.multiply(data, bscale, data)
    data += bzero
    return data


def decode_timestamp(ts_bytes):
    """
    Decode timestamp tuple from values saved in FITS file

    The timestamp is originally encoded to bytes as a series of
    32bit (4 bytes) unsigned integers in little endian byte format.

    However, this is then stored as fake pixels in a FITS file, which
    performs some mangling of the data, since FITS assumes 16bit (2 byte)
    integers, and has no way to store unsigned integers. The following
    mangling occurs:

    - decode the timestamp byte string as two 16bit (2 bytes) little-endian unsigned integers;
    - subtract 32768 from each integer;
    - encode these integers as two 16bit signed integers in BIG ENDIAN format;
    - save to file as fits data.

    This routine reverses this process to recover the original timestamp tuple. We have to
    take some care because of all the endian-swapping going on. For example, the number 27
    starts off as \x1b\x00\x00\x00, which is interpreted by the FITS save process as (27, 0).
    If we ignore the signing issue for clarity, then (27, 0) encoded in big endian format is
    \x00\x1b, \x00\x00 so we've swapped the byte pairs around.

    The steps taken by this routine are:

    - decode timestamp string as big endian 16bit integers
    - add 32768 to each value
    - encode these values as little endian 16bit unsigned integers
    - re-interpret the new byte string as 32bit, little-endian unsigned integers

    Parameters
    ----------
    ts_bytes: bytes
        a Python bytes object which contains the timestamp bytes as written in the
        FITS file

    Returns
    --------
    timestamp : tuple
        a tuple containing the (frameCount, timeStampCount,
                                years, day_of_year, hours, mins,
                                seconds, nanoseconds) values.
    """
    buf = struct.pack('<' + 'H'*16, *(val + 32768 for val in struct.unpack('>'+'h'*16, ts_bytes)))
    return struct.unpack('<' + 'I'*8, buf)
