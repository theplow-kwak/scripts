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


class WaiInfo:
    col_names = ['timestamp', 'cum_host_writes', 'cum_nand_written', 'cum_nand_erased',
                 'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai']
    keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

    def __init__(self, dev='/dev/nvme0'):
        self.nvme = dev
        self.__wai_info = 'nvme hynix wai-information {}'.format(self.nvme).split()
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
        wei_proc = self.sudo_exec.Popen(self.__wai_info, wait=False)
        data, err = wei_proc.communicate()
        if len(data):
            __data = dict(self.keyval_exp.findall(str(data)))
            for k, v in __data.items():
                __data[k] = self.__to_num(v)
            return __data
        else:
            print(err)

    def calc(self, end, start=None):
        if not start:
            start = self.last_data
        nand_written = (end['nand_written'] - start['nand_written'])
        host_writes = (end['host_writes'] - start['host_writes'])
        nand_erased = (end['nand_erased'] - start['nand_erased'])
        if host_writes:
            waf = round(nand_written / host_writes, 2)
            wai = round(nand_erased / host_writes, 2)
            return nand_written, host_writes, nand_erased, waf, wai
        else:
            return nand_written, host_writes, nand_erased, 0, 0

    def update(self, printout=False):
        self.__current = self.get_data()

        if self.__current is not None:
            __time = round(time.time(), 6)
            # elapstime = __time - self.last_time

            nand_written, host_writes, nand_erased, waf, wai = self.calc(self.__current)
            if host_writes:
                self.datas.loc[self.index] = [__time, self.last_data['host_writes'], self.last_data['nand_written'], self.last_data['nand_erased'],
                                              host_writes, nand_written, nand_erased, waf, wai]
                if printout is True:
                    print('{5:<20} {0:>12} {1:>12} {2:>12} {3:>5.3} {4:>5.3}'.format(
                        host_writes, nand_written, nand_erased, waf, wai, __time))
                    # print(self.datas.loc[self.index])
                self.last_data = self.__current
                self.last_time = __time
                self.index += 1
            return self.__current


def capture_wai(wai_info, outfile, verbose=False, stop=False):
    tag = time.time()

    if verbose:
        # header
        print('{5:^20} {0:>12} {1:>12} {2:>12} {3:>5} {4:>5}'.format(
            'host_writes', 'nand_written', 'nand_erased', 'waf', 'wai', 'timestamp'))

    try:
        while 1:
            if (time.time() - tag) > 60:
                wai_info.update(verbose)
                wai_info.datas.to_csv(outfile, index=False)
                tag = time.time()
            if stop():
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    wai_info.update(verbose)
    wai_info.datas.to_csv(outfile, index=False)


def main(outpath='./'):

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-v', '--visualize', action='store_true', help='display the reports')
    argparser.add_argument('-o', '--outfile', help='output file')
    argparser.add_argument('-f', '--filename', nargs='+', help='trace data file (csv)')
    argparser.add_argument('-d', '--display', action='store_true', help='verbose display')
    args = argparser.parse_args()

    outfilename = outpath + "waf_info" + time.strftime("-%m%d-%H%M") + ".csv"

    if args.outfile:
        outfilename = args.outfile

    wai_info = WaiInfo()
    start = wai_info.last_data


    capture_wai(wai_info, outfilename, args.display)

    print()
    print('host_writes: {0[1]}, nand_written: {0[0]}, nand_erased: {0[2]}, waf: {0[3]}, wai: {0[4]}'.format(wai_info.calc(wai_info.last_data, start)))


if __name__ == "__main__":

    main()
