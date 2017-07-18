# talk to honeywell temperature monitor
from __future__ import absolute_import, unicode_literals, print_function, division
from .utils import DriverError
import six
if not six.PY3:
    from pymodbus.constants import Endian
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.client.sync import ModbusTcpClient as ModbusClient
else:
    from pymodbus3.constants import Endian
    from pymodbus3.payload import BinaryPayloadDecoder
    from pymodbus3.client.sync import ModbusTcpClient as ModbusClient


class Honeywell:
    def __init__(self, address, port):
        self.client = ModbusClient(address, port=port)
        # list mapping pen ID number to address
        # TODO: complete
        self.pen_addresses = [0x18C1, 0x18C2, 0x18C3, 0x18C4]
        self.unit_id = 0x01  # allows us to address different units on the same network
        # check we can connect!
        try:
            self.client.connect()
        except Exception as err:
            raise DriverError(str(err))
        finally:
            self.client.close()

    def read_pen(self, pen_id):
        """
        Read a pen value from the client

        Raises
        ------
        DriverError
            When reading fails
        """
        try:
            self.client.connect()
            address = self.pen_addresses[pen_id]
            value = self.get_pen(address)
        except Exception as err:
            raise DriverError(str(err))
        finally:
            self.client.close()
        return value

    def get_pen(self, address):
        result = self.client.read_input_registers(address, 2, unit=self.unit_id)
        decoder = BinaryPayloadDecoder.fromRegisters(result.registers,
                                                     endian=Endian.Big)
        return decoder.decode_32bit_float()

    def __iter__(self):
        """
        Iterator so that CCD temps can be looped over
        """
        try:
            self.client.connect()
            for address in self.pen_addresses:
                yield self.get_pen(address)
        except StopIteration:
            raise
        except Exception as err:
            raise DriverError(str(err))
        finally:
            self.client.close()
