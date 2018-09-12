#!/usr/bin/python3

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import re
import os
import argparse
import subprocess
import threading
import signal
import time
import getpass
import pandas as pd


nvme_path = '/mnt/nvme'
nvme_dev = 'nvme0'
discard = ',discard'

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
    col_names = ['timestamp', 'cum_host_writes', 'cum_nand_written', 'cum_nand_erased',
                 'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai']
    keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

    def __init__(self, dev='/dev/nvme0'):
        self.nvme = dev
        self.script = 'nvme hynix wai-information {}'.format(self.nvme).split()
        self.datas = pd.DataFrame(columns=self.col_names)
        self.index = 0
        self.last_time = time.time()
        self.sudo_exec = SudoProcess()
        self.last_data = self.get_data()

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
            return list(start['host_writes'], start['nand_written'], start['nand_erased'], host_writes, nand_written, nand_erased, waf, wai)

    def update(self, outfile, verbose=False):
        self.__current = self.get_data()

        if self.__current is not None:
            datas = self.get_diff(self.__current)
            if datas:
                __time = round(time.time(), 6)
                __result = [__time] + datas
                outfile.writerow(__result)
                if verbose is True:
                    print('{0:<20} {4:>12} {5:>12} {6:>12} {7:>5.3} {8:>5.3}'.format(*__result))
                self.last_data = self.__current
                self.last_time = __time
                self.index += 1
                return __result


def capture_wai(wai_info, filename, verbose=False, stop=False):
    import csv

    if verbose:
        # header
        print('{0:^20} {1:>12} {2:>12} {3:>12} {4:>5} {5:>5}'.format(
            'timestamp', 'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai'))

    fout = open(filename, 'w')
    outfile = csv.writer(fout)
    outfile.writerow(['timestamp', 'cum_host_writes', 'cum_nand_written', 'cum_nand_erased',
                 'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai'])

    uid = os.environ.get('SUDO_UID')
    gid = os.environ.get('SUDO_GID')
    if uid is not None:
        os.chown(filename, int(uid), int(gid))

    tag = time.time()
    try:
        while 1:
            if (time.time() - tag) > 60:
                wai_info.update(outfile, verbose)
                tag = time.time()
            if stop():
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    wai_info.update(outfile, verbose)


def main(outpath='./'):

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--display', action='store_true', help='display the reports')
    argparser.add_argument('-o', '--outfile', help='output file')
    argparser.add_argument('-f', '--filename', help='trace data file (csv)')  # nargs='+',
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose display')
    args = argparser.parse_args()

    outfilename = outpath + "waf_info" + time.strftime("-%m%d-%H%M") + ".csv"

    if args.outfile:
        outfilename = args.outfile

    wai_info = WaiInfo()
    start = wai_info.last_data


    stop_threads = False
    capture_wai(wai_info, outfilename, args.verbose, lambda: stop_threads)


if __name__ == "__main__":

    main()
