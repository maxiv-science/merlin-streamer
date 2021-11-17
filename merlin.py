import os
import time
import h5py
import socket 
import select
import asyncio
import bitshuffle
import numpy as np
from multiprocessing import Process, Pipe

DSET_NAME = '/entry/measurement/Merlin/data'

def flush_socket(sock):
    total = 0
    while True:
        fds = select.select([sock], [], [], 0)
        if not fds[0]:
            break
        total += len(sock.recv(1024))
    print('cleared %u bytes from the socket' %total)

# special receive function to work around all the Merlin data format quirks
def recv(sock):
    # read from socket until we find the beginning of the header: MPX
    mpx = b'MPX'
    header_char = 0
    header = bytearray(14)
    view = memoryview(header)
    while header_char < 3:
        sock.recv_into(view[header_char:], 1)
        if header[header_char] == mpx[header_char]:
            header_char += 1
        else:
            header_char = 0
            print('Unexpected charater in header')
            print(header)
            
    # read rest of the header, exclude \x00 string terminators in the middle
    while header_char < 13:
        sock.recv_into(view[header_char:], 1)
        if header[header_char:header_char+1] != b'\x00':
            header_char += 1
    sock.recv_into(view[header_char:], 1)
    
    try:
        length = int(header[4:])
    except:
        print('Strange header!!')
        after = sock.recv(1024)
        print(header)
        print(after)
        fh = open('error.log', 'wb')
        fh.write(b'header\n')
        fh.write(header)
        fh.write('\n')
        fh.write(b'after header\n')
        fh.write(after)
        fh.close()
        exit(-1)
    
    # read rest of the message
    data = bytearray(length)
    toread = length
    view = memoryview(data)
    while toread:
        nbytes = sock.recv_into(view, toread)
        view = view[nbytes:]
        toread -= nbytes
    return data
    
def get_data(sock):
    payload = recv(sock)
    header_id = payload[1:4]
    if header_id == b'HDR':
        #print('Acquistion header')
        return None
    if header_id == b'MQ1':
        #print('Frame header')
        #added one because they forgot to count the , in the beginning for the offset
        data_offset = int(payload[12:17]) + 1
        pixel_depth = payload[31:34]
        if pixel_depth == b'U16':
            dtype = np.dtype('>u2')
        elif pixel_depth == b'U32':
            dtype = np.dtype('>u4')
        img = np.frombuffer(payload, dtype=dtype, offset=data_offset).reshape(515, 515)
        # convert to little endian
        return img.byteswap(inplace=True).newbyteorder()


def handle_image(img, fh, dset):
    if not dset:
        shape = (0,) + img.shape
        maxshape = (None,) + img.shape
        chunks = (1,) + img.shape
        dset = fh.create_dataset(DSET_NAME, chunks=chunks,
                                 shape=shape, maxshape=maxshape,
                                 compression=bitshuffle.BSHUF_H5FILTER,
                                 compression_opts=(0, bitshuffle.BSHUF_H5_COMPRESS_LZ4),
                                 dtype=img.dtype)
                    
    compressed = bitshuffle.compress_lz4(img)
    current = dset.shape[0]
    dset.resize(current+1, axis=0)
    dset.id.write_direct_chunk((current, 0, 0), compressed.tobytes())
    return dset

def print_color(msg, color):
    cols = {'red': '\033[91m',
            'green': '\033[92m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'black': '\033[0m'}
    print(cols[color], msg, cols['black'])

def worker(host, pipe):
    def print(msg):
        print_color('worker: %s'%msg, 'blue')
    print('Worker process started')
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.connect((host, 6342))
    #flush_socket(data_sock)
    writing = False
    while True:
        config = pipe.recv()
        print('received: %s' % config)
        filename = config['filename']
        if filename:
            writing = True
            if os.path.exists(filename):
                fh = h5py.File(filename, 'r+')
                dset = fh[DSET_NAME]
            else:
                fh = h5py.File(filename, 'w')
                dset = None
        else:
            writing = False
                
        acquired = 0
        timeout = None
        while acquired < config['nframes']:
            rfs, _, _ = select.select([data_sock, pipe.fileno()], [], [], timeout)
            # timout select
            if not rfs:
                print('timeout select')
                break
            for fd in rfs:
                if fd is data_sock:
                    print('calling get_data()')
                    img = get_data(data_sock)
                    print('get_data() returned %s' % (None if img is None else (img.shape,)))
                    if img is None:
                        continue
                    acquired += 1
                    if writing:
                        dset = handle_image(img, fh, dset)
                    print('acquired %s' % acquired)
                    
                if fd is pipe.fileno():
                    msg = pipe.recv()
                    print('pipe % s' % msg)
                    timeout = 2.0 * msg['acquisition_time']
                    
        if writing:
            fh.close()
        pipe.send('Done')


class Merlin:
    def __init__(self, host, debug=False):
        self.color = 'red'
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_sock.connect((host, 6341))
        #flush_socket(self.control_sock)
        self.pipe, worker_pipe = Pipe(duplex=True)
        loop = asyncio.get_event_loop()
        # event gets set when there's something to read on the pipe:
        self.event = asyncio.Event()
        loop.add_reader(self.pipe.fileno(), self.event.set)
        self.process = Process(target=worker, args=(host, worker_pipe))
        self.process.start()
        self.filename = ''
        self.do_debug = debug

    def debug(self, msg):
        if self.do_debug:
            print_color('Merlin object: %s'%msg, self.color)

    def check_response(self, response):
        if response[-1] == '0':
            pass
        elif response[-1] == '1':
            raise RuntimeError('Sent a command, but Merlin was busy (code 1)')
        elif response[-1] == '2':
            raise RuntimeError('Sent a command that Merlin didnt recognize (code 2)')
        elif response[-1] == '3':
            raise RuntimeError('Sent a command but parameter was out of range (code 3)')
            
    def get(self, name):
        msg = b'MPX,%010d,GET,%s' %(len(name)+5, name)
        self.control_sock.send(msg)
        response = recv(self.control_sock).decode()
        parts = response.split(',')
        self.check_response(response)
        return parts[-2]
    
    def set(self, name, value):
        self.debug('setting %s=%s' % (name.decode(), value))
        msg = b',SET,%s,%s' % (name, str(value).encode())
        msg = b'MPX,%010d%s' % (len(msg), msg)
        self.debug('sending: "%s"' % msg)
        self.control_sock.send(msg)
        response = recv(self.control_sock).decode()
        self.check_response(response)

    def cmd(self, cmd):
        msg = b'MPX,%010d,CMD,%s' %(len(cmd)+5, cmd)
        self.control_sock.send(msg)
        response = recv(self.control_sock).decode()
        self.check_response(response)
        return int(response[-1])
    
    def arm(self):
        self.debug('entering arm()')
        self.cmd(b'STARTACQUISITION')
        # loop until detectorstatus is armed
        time.sleep(100.0e-3)
        while True:
            status = int(self.get(b'DETECTORSTATUS'))
            if status == 4 or status == 1:
                break
            self.debug('arm status: %s' % status)
            time.sleep(100.0e-6)
        self.debug('arm status: %s' % status)
        self.debug('leaving arm()')
        
    async def start(self, nframes):
        self.debug('entering start()')
        self.pipe.send({'filename': self.filename, 'nframes': nframes})
        trigger_start = int(self.get(b'TRIGGERSTART'))
        if trigger_start == 5:
            self.debug('soft triggering')
            self.cmd(b'SOFTTRIGGER')
        await self.event.wait()
        self.event.clear()
        try:
            ret = ''
            ret = self.pipe.recv()
        except EOFError:
            self.debug('got nothing back from the worker. but how is that possible, if the event is set then pipe.fileno must be ready, right?')
            pass
        self.debug('recv: %s' % ret)
        self.debug('leaving start()')
        
    def stop(self):
        # convert from ms to seconds
        acquisition_time = float(self.get(b'ACQUISITIONTIME')) * 1.0e-3
        self.cmd(b'STOPACQUISITION')
        self.pipe.send({'command': 'stop', 'acquisition_time': acquisition_time})

if __name__ == '__main__':
    merlin = Merlin('172.16.126.78')
    print('result', merlin.get(b'NUMFRAMESPERTRIGGER'))
