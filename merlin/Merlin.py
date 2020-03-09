import socket
import select
import time
import numpy as np

BUF_SIZE = 2048

class Merlin(object):

    def __init__(self, host='b303a-a100384-dia-detpicu-02.maxiv.lu.se',
                       cmd_port=6341, dat_port=6342, debug=False):
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_sock.connect((host, cmd_port))
        self.dat_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dat_sock.connect((host, dat_port))
        self.debug_on = debug

    def debug(self, *args):
        """
        Prints if debug is enabled.
        """
        if self.debug_on:
            print(*args)

    def set_prop(self, name, val):
        """
        Set a Merlin property on the command port.
        """
        cmd = b',SET,%s,%s' % (name.encode(), str(val).encode())
        cmd_len = len(cmd)
        cmd = b'MPX,%010u%s' % (cmd_len, cmd)
        self.debug('sending:', cmd)
        self.cmd_sock.send(cmd)
        response = self.cmd_sock.recv(BUF_SIZE)
        self.debug('received:', response)
        ok = (response[-1] == b'0')
        return ok

    def get_prop(self, name):
        """
        Get a Merlin property from the command port.
        """
        cmd = b'MPX,%010u,GET,%s' % (len(name)+5, name.encode())
        self.debug('sending:', cmd)
        self.cmd_sock.send(cmd)
        response = self.cmd_sock.recv(BUF_SIZE).decode()
        self.debug('received:', response)
        result = response.split(',')
        if not result[-1] == '0':
            raise Exception('Could not get property.\n%s\nreturned\n%s' % (cmd, result))
        try:
            return eval(result[-2])
        except NameError:
            return result[-2]

    def send_command(self, cmd):
        """
        Send a command on the command port.
        """
        cmd = b'MPX,%010u,CMD,%s' % (len(cmd)+5, cmd.encode())
        self.debug('sending:', cmd)
        self.cmd_sock.send(cmd)

    def flush_data_socket(self):
        """
        Empty the data socket to get rid of old shit.
        """
        total = 0
        while True:
            ready = select.select([self.dat_sock], [], [], .05)
            if not ready[0]:
                break
            total += len(self.dat_sock.recv(1024))
        print('cleared %u bytes from the data socket'%total)


if __name__ == '__main__':
    m = Merlin()

