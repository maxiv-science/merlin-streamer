import os
import zmq
import time
import h5py
import socket 
import select
import bitshuffle
import numpy as np
from multiprocessing import Process

def flush_socket(sock):
    total = 0
    while True:
        fds = select.select([sock], [], [], 0)
        if not fds[0]:
            break
        total += len(sock.recv(1024))
    print('cleared %u bytes from the socket' %total)


def recv(sock):
    header = sock.recv(14)
    #print(header)
    assert header[:3] == b'MPX', header
    length = int(header[4:])
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
        print('Acquistion header')
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


def worker(host):
    dset_name = '/entry/measurement/Merlin/data'
    print('Worker process started')
    context = zmq.Context()
    rep_socket = context.socket(zmq.REP)
    rep_socket.connect('ipc://merlin.ipc')
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.connect((host, 6342))
    flush_socket(data_sock)
    writing = False
    while True:
        config = rep_socket.recv_pyobj()
        print(config)
        filename = config['filename']
        if filename:
            writing = True
            if os.path.exists(filename):
                fh = h5py.File(filename, 'r+')
                dset = fh[dset_name]
            else:
                fh = h5py.File(filename, 'w')
                dset = None
        else:
            writing = False
                
            
        acquired = 0
        while acquired < config['nframes']:
            img = get_data(data_sock)
            if img is None:
                continue
            acquired += 1
            if writing:
                if not dset:
                    shape = (0,) + img.shape
                    maxshape = (None,) + img.shape
                    chunks = (1,) + img.shape
                    dset = fh.create_dataset(dset_name, chunks=chunks,
                                             shape=shape, maxshape=maxshape,
                                             compression=bitshuffle.BSHUF_H5FILTER,
                                             compression_opts=(0, bitshuffle.BSHUF_H5_COMPRESS_LZ4),
                                             dtype=img.dtype)
                    
                compressed = bitshuffle.compress_lz4(img)
                current = dset.shape[0]
                dset.resize(current+1, axis=0)
                dset.id.write_direct_chunk((current, 0, 0), compressed.tobytes())
                
            print('acquired', acquired)
        if writing:
            fh.close()
        rep_socket.send_pyobj('Done')
        

class Merlin:
    def __init__(self, host):
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_sock.connect((host, 6341))
        flush_socket(self.control_sock)
        self.context = zmq.Context()
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.bind('ipc://merlin.ipc')
        self.process = Process(target=worker, args=(host,))
        self.process.start()
        self.filename = ''
            
    def get(self, name):
        msg = b'MPX,%010d,GET,%s' %(len(name)+5, name)
        self.control_sock.send(msg)
        #print(msg)
        response = recv(self.control_sock).decode()
        #print(response)
        parts = response.split(',')
        assert parts[-1] == '0'
        return parts[-2]
    
    def set(self, name, value):
        msg = b',SET,%s,%s' % (name, str(value).encode())
        msg = b'MPX,%010d%s' % (len(msg), msg)
        self.control_sock.send(msg)
        response = recv(self.control_sock).decode()
        assert response[-1] == '0', 'set %s failed with code %s' %(name, response[-1])

    def cmd(self, cmd):
        msg = b'MPX,%010d,CMD,%s' %(len(cmd)+5, cmd)
        self.control_sock.send(msg)
        response = recv(self.control_sock).decode()
        assert response[-1] == '0'
        return int(response[-1])
    
    def arm(self):
        self.cmd(b'STARTACQUISITION')
        # loop until detectorstatus is armed
        time.sleep(100.0e-3)
        while True:
            status = int(self.get(b'DETECTORSTATUS'))
            if status == 4 or status == 1:
                break
            print('arm status', status)
            time.sleep(100.0e-6)
        print('status', status)
        
    def start(self, nframes):
        self.req_socket.send_pyobj({'filename': self.filename, 'nframes': nframes})
        trigger_start = int(self.get(b'TRIGGERSTART'))
        if trigger_start == 5:
            print('softtrigger')
            self.cmd(b'SOFTTRIGGER')
        print('recv', self.req_socket.recv_pyobj())

if __name__ == '__main__':
    merlin = Merlin('172.16.126.78')
    print('result', merlin.get(b'NUMFRAMESPERTRIGGER'))
