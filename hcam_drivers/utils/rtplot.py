from __future__ import print_function, absolute_import, division
import socketserver
import http.server
import socket
import errno

from . import DriverError


class RtplotHandler(http.server.BaseHTTPRequestHandler):
    """
    Handler for requests from rtplot. It accesses the window
    parameters via the 'server' attribute; the Server class
    that comes next stores these in on instantiation.
    """
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        wins = self.server.instpars.getRtplotWins()
        if wins == '':
            self.wfile.write('No valid data available\r\n')
        else:
            self.wfile.write(wins)


class RtplotServer(socketserver.TCPServer):
    """
    Server for requests from rtplot.
    The response delivers the binning factors, number of windows and
    their positions.
    """
    def __init__(self, instpars, port):
        # '' opens port on localhost and makes it visible
        # outside localhost
        try:
            super(RtplotServer, self).__init__(('', port), RtplotHandler)
            self.instpars = instpars
        except socket.error as err:
            errorcode = err[0]
            if errorcode == errno.EADDRINUSE:
                message = str(err) + '. '
                message += 'Failed to start the rtplot server. '
                message += 'There may be another instance of usdriver running. '
                message += 'Suggest that you shut down usdriver, close all other instances,'
                message += ' and then restart it.'
            else:
                message = str(err)
                message += 'Failed to start the rtplot server'

            raise DriverError(message)
        print('rtplot server started')

    def run(self, g):
        while True:
            try:
                self.serve_forever()
            except Exception as e:
                g.clog.warn('RtplotServer.run', e)
