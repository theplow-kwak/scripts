#!/usr/bin/python3

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import os, re
import argparse
import subprocess
import threading
import time
import getpass
import pandas as pd


class SudoProcess:
    sudo_passwd = None

    def __init__(self, shell=False, passwd=None):
        if shell:
            self.sudo_cmd = 'sudo -S sh -c'.split()
        else:
            self.sudo_cmd = 'sudo -S'.split()
        if passwd:
            SudoProcess.sudo_passwd = passwd
        if SudoProcess.sudo_passwd is None:
            SudoProcess.sudo_passwd = getpass.getpass('password:')

    def Popen(self, commands, wait=True):
        # print(self.sudo_cmd+commands)
        echo_passwd = subprocess.Popen(['echo', self.sudo_passwd], stdout=subprocess.PIPE)
        try:
            cmd = subprocess.Popen(self.sudo_cmd+commands, stdin=echo_passwd.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if wait:
                cmd.communicate()
            else:
                return cmd
        except:
            print('process open error! {}'.format(commands))


class RingBuffer:
    """ class that implements a not-yet-full buffer """
    def __init__(self,size_max):
        self.max = size_max
        self.len = 0
        self.data = []

    class __Full:
        """ class that implements a full buffer """
        def append(self, x):
            """ Append an element overwriting the oldest one. """
            self.data[self.cur] = x
            self.cur = (self.cur+1) % self.max
        def get(self):
            """ return list of elements in correct order """
            return self.data[self.cur:]+self.data[:self.cur]

    def append(self,x):
        """append an element at the end of the buffer"""
        self.data.append(x)
        self.len += 1
        if len(self.data) == self.max:
            self.cur = 0
            # Permanently change self's class from non-full to full
            self.__class__ = self.__Full

    def get(self):
        """ Return a list of elements from the oldest to the newest. """
        return self.data


class WaiInfo:
    keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

    def __init__(self, dev='/dev/nvme0'):
        self.nvme = dev
        self.script = 'nvme hynix wai-information {}'.format(self.nvme).split()
        self.index = 0
        self.last_time = time.time()
        self.sudo_exec = SudoProcess()
        self.first_data = self.last_data = self.get_data()

    def __to_num(self, str_num):
        try:
            return float(str_num) if '.' in str_num else int(str_num, 0)
        except:
            return str_num

    def get_data(self):
        wei_proc = self.sudo_exec.Popen(self.script, wait=False)
        data, err = wei_proc.communicate()
        if len(data):
            __data = dict(self.keyval_exp.findall(str(data)))
            for k, v in __data.items():
                __data[k] = self.__to_num(v)
            return __data
        else:
            print(err)

    def get_diff(self, end, start=None):
        if not start:
            start = self.last_data
        host_writes = (end['host_writes'] - start['host_writes'])
        nand_written = (end['nand_written'] - start['nand_written'])
        nand_erased = (end['nand_erased'] - start['nand_erased'])
        if host_writes:
            waf = round(nand_written / host_writes, 2)
            wai = round(nand_erased / host_writes, 2)
        else:
            waf = 0.0
            wai = 0.0
        return [start['host_writes'], start['nand_written'], start['nand_erased'], host_writes, nand_written, nand_erased, waf, wai]

    def update(self):
        self.__current = self.get_data()

        if self.__current is not None:
            datas = self.get_diff(self.__current)
            __time = round(time.time(), 6)
            __result = [__time] + datas
            self.last_data = self.__current
            self.last_time = __time
            self.index += 1
            return __result


class CaptureWai(threading.Thread):

    def __init__(self, nvme='dev/nvme0', filename=None, verbose=False, testmode=False):
        super().__init__()
        self.exit = threading.Event()
        self.verbose = verbose
        self.filename = filename
        self.wai_info = WaiInfo(nvme)
        self.interval = 60
        self.columns = ['timestamp', 'cum_host_writes', 'cum_nand_written', 'cum_nand_erased',
                          'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai']

        self.testmode = testmode
        if testmode:
            self.verbose = True
            self.interval = 1

    def update(self, forceupdate=False):
        result = self.wai_info.update()
        if (result[4] > 0) or forceupdate:
            if not self.testmode:
                self.outfile.writerow(result)
            if self.verbose:
                print('{0:<20} {1:>12} {2:>12} {3:>12} {4:>12} {5:>12} {6:>12} {7:>5.3} {8:>5.3}'.format(*result))

    def run(self):
        import csv

        if self.filename is None:
            self.filename = "waf_info" + time.strftime("-%m%d-%H%M") + ".csv"

        fout = open(self.filename, 'w')
        self.outfile = csv.writer(fout)
        self.outfile.writerow(self.columns)
        if self.verbose:
            # header
            print('{0:^20} {1:>12} {2:>12} {3:>12} {4:>12} {5:>12} {6:>12} {7:>5} {8:>5}'.format(*self.columns))
        self.update(True)

        uid = os.environ.get('SUDO_UID')
        gid = os.environ.get('SUDO_GID')
        if uid is not None:
            os.chown(self.filename, int(uid), int(gid))

        tag = time.time()
        while not self.exit.is_set():
            if (time.time() - tag) > self.interval:
                self.update()
                tag = time.time()
            time.sleep(0.1)

        self.update(True)
        fout.close()

    def shutdown(self):
        self.exit.set()


nvme_path = '/mnt/nvme'
discard = ',discard'

def main():
    nvme_dev = '/dev/nvme0'

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--display', action='store_true', help='display the reports')
    argparser.add_argument('-o', '--outfile', help='output file')
    argparser.add_argument('-p', '--path', help='target path')
    argparser.add_argument('-n', '--nvme', help='nvme device name')
    argparser.add_argument('-f', '--filename', help='trace data file (csv)')  # nargs='+',
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose display')
    argparser.add_argument('-t', '--testmode', action='store_true', help='test mode: do not save data')
    args = argparser.parse_args()

    outfilename = "waf_info" + time.strftime("-%m%d-%H%M") + ".csv"

    if args.outfile:
        outfilename = args.outfile

    if args.path:
        out = subprocess.Popen('df {}'.format(args.path).split(), stdout=subprocess.PIPE).communicate()
        m = re.search(r'(/[^\s]+)\s', str(out))
        if m:
            nvme_dev = m.group(1)

    if args.nvme:
        nvme_dev = args.nvme

    process = CaptureWai(nvme_dev, outfilename, args.verbose, args.testmode)
    process.start()

    try:
        while 1:
            pass
    except KeyboardInterrupt:
        pass

    process.shutdown()
    process.join()



if __name__ == "__main__":

    main()
