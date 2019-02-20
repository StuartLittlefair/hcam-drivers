import serial
import threading

class NewportError(Exception):
    '''
    Class to represent errors from the controller

    Errors come in the form (code, timestamp, MESSAGE).
    e.g 0, 451322, NO ERROR DETECTED
    '''
    def __init__(self, string):
        self._string = string
        code, ts, msg = string.split(',')
        if len(code) == 3:
            self.axis = int(code[0])
            self.code = int(code[1:])
        else:
            self.axis = None
            self.code = code
        self.timestamp = int(ts.strip())
        self.message = msg.strip()
        
