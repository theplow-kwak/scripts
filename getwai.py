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

from bmcore import *


class WaiInfo:
    keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

    def __init__(self, dev='/dev/nvme0'):
        self.nvme = dev
        self.sudo_exec = SudoProcess()
        self.script = 'nvme hynix wai-information {}'.format(self.nvme).split()
        self.last_data = {'nand_written': 0, 'host_writes': 0, 'nand_erased': 0}

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
        return host_writes, nand_written, nand_erased, waf, wai


class CaptureWai(CaptureThread):
    name = 'wai'
    interval = 60
    logformat = '{0:<20} {1:>16} {2:>16} {3:>16} {4:>12} {5:>12} {6:>12} {7:>5.3} {8:>5.3}'
    header = ['timestamp', 'cum_host_writes', 'cum_nand_written', 'cum_nand_erased',
              'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai']

    def __init__(self, nvme='/dev/nvme0', filename=None, verbose='t'):
        super().__init__(filename, verbose)
        self.count = 0
        self.wai_info = WaiInfo(nvme)
        self.wai_start = self.wai_last = self.wai_info.get_data()

    def work(self):
        if (time.time() - self.tag) > self.interval:
            self.wai_current = self.wai_info.get_data()
            host_writes, nand_written, nand_erased, waf, wai = self.wai_info.get_diff(self.wai_current, self.wai_last)
            if host_writes:
                self.logging([self.tag, self.wai_last['host_writes'], self.wai_last['nand_written'], self.wai_last['nand_erased'], host_writes, nand_written, nand_erased, waf, wai])
                self.wai_last = self.wai_current
            self.tag = time.time()
        time.sleep(0.001)

    def shutdown(self):
        self.wai_current = self.wai_info.get_data()
        host_writes, nand_written, nand_erased, waf, wai = self.wai_info.get_diff(self.wai_current, self.wai_last)
        self.logging(
            [time.time(), self.wai_last['host_writes'], self.wai_last['nand_written'], self.wai_last['nand_erased'],
             host_writes, nand_written, nand_erased, waf, wai])
        self.wai_last = self.wai_current

        super().shutdown()

    def summary(self):
        print()
        print('start', self.wai_start)
        print('end  ', self.wai_last)
        print('  Host writes : ', self.wai_last['host_writes'] - self.wai_start['host_writes'])
        print('  NAND written: ', self.wai_last['nand_written'] - self.wai_start['nand_written'])
        print('  NAND erased : ', self.wai_last['nand_erased'] - self.wai_start['nand_erased'])


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
    argparser.add_argument('-v', '--verbose', nargs='?', default='s', help='verbose display')
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

    wai_info = CaptureWai(nvme_dev, filename=outfilename, verbose=args.verbose)
    wai_info.start()

    try:
        while 1:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    wai_info.shutdown()
    wai_info.join()
    wai_info.summary()


if __name__ == "__main__":

    main()
