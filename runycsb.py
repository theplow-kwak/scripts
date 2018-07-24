#!/usr/bin/python3

import re
import os
import argparse
import subprocess
import threading
import signal
import time
import getpass
import pandas as pd


class SudoProcess:
    sudo_passwd = None

    def __init__(self, shell=False):
        if shell:
            self.sudo_cmd = 'sudo -S sh -c'.split()
        else:
            self.sudo_cmd = 'sudo -S'.split()
        if SudoProcess.sudo_passwd is None:
            SudoProcess.sudo_passwd = getpass.getpass('password:')

    def Popen(self, commands, wait=True):
        print(self.sudo_cmd+commands)
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
    col_names = ['lapstime', 'cum_nand_written', 'cum_host_writes', 'cum_nand_erased', 'nand_written', 'host_writes',
                 'nand_erased', 'waf', 'wai']
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
            waf = nand_written / host_writes
            wai = nand_erased / host_writes
            return nand_written, host_writes, nand_erased, waf, wai
        else:
            return nand_written, host_writes, nand_erased, 0, 0

    def update(self):
        self.__current = self.get_data()

        if self.__current is not None:
            __time = time.time()
            lapstime = __time - self.last_time

            nand_written, host_writes, nand_erased, waf, wai = self.calc(self.__current)
            self.datas.loc[self.index] = [lapstime, self.last_data['nand_written'], self.last_data['host_writes'], self.last_data['nand_erased'], nand_written, host_writes, nand_erased, waf, wai]
            self.last_data = self.__current
            self.last_time = __time
            self.index += 1
            return self.__current


nvme_path = '/media/dhkwak/nvme'
nvme_dev = 'nvme0'
discard = ',discard'

nvme_enable = ['echo 1 > /sys/kernel/debug/tracing/events/nvme/enable']
trace_on = ['echo 1 > /sys/kernel/debug/tracing/tracing_on']
clear_trace = ['echo 1 > /sys/kernel/debug/tracing/trace']
stream_on = ['echo 1 > /sys/module/nvme_core/parameters/streams']
stream_off = ['echo 0 > /sys/module/nvme_core/parameters/streams']

trim = 'fstrim -v {}'.format(nvme_path).split()

#ycsb_workload = 'workloads/nvme_test'
ycsb_workload = 'workloads/workloadf'

ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, nvme_path).split()
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, nvme_path).split()

def capture_wai(wai_info, outfile, stop):
    tag = time.time()
    while True:
        if (time.time() - tag) > 60:
            wai_info.update()
            wai_info.datas.to_csv(outfile, index=False)
            tag = time.time()
        if stop():
            print('stop capture_wai')
            break
        time.sleep(0.1)
    wai_info.update()
    wai_info.datas.to_csv(outfile, index=False)


def runtest(loop=1, load=False, outpath='./'):

    for i in range(loop):
        starttime = time.time()
        wai_info = WaiInfo()
        start = wai_info.last_data

        outfile = outpath + "waf_info_{}".format(i) + time.strftime("-%m%d-%H%M") + ".csv"
        outlog = outpath + "ycsblog_{}".format(i) + time.strftime("-%m%d-%H%M") + ".log"
        outnvme = outpath + "nvme_{}".format(i) + time.strftime("-%m%d-%H%M") + ".csv"
        file = open(outlog, "w")
        nvmeparser = subprocess.Popen('{}/projects/scripts/nvmesnoop.py -o {}'.format(os.getenv("HOME"), outnvme).split())
        if load:
            ycsb = subprocess.Popen(ycsb_load, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        else:
            ycsb = subprocess.Popen(ycsb_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        stop_threads = False
        tmp = threading.Thread(target=capture_wai, args=(wai_info, outfile, lambda: stop_threads))
        tmp.start()

        while ycsb.poll() is None:
            logdata = ycsb.stdout.readline()
            print(logdata.strip())
            file.write(logdata)

        ycsb.wait()
        stop_threads = True
        time.sleep(10)

        nvmeparser.send_signal(signal.SIGINT)


def mount(nvme_dev=nvme_dev, nvme_path=nvme_path, discard=discard):
    sudo_exec = SudoProcess()
    sudo_exec.Popen('mount -o rw,nosuid,nodev{2} /dev/{0}n1p1 {1}'.format(nvme_dev, nvme_path, discard).split())

def umount(nvme_path=nvme_path):
    sudo_exec = SudoProcess()
    sudo_exec.Popen('umount {}'.format(nvme_path).split())

def main(workload, ycsbpath):
    sudo_shell = SudoProcess(True)
    sudo_shell.Popen(nvme_enable)
    sudo_shell.Popen(trace_on)
    sudo_exec = SudoProcess()

    testloop = 6
    mount()
    subprocess.call('rm -rdf {}/*'.format(nvme_path), shell=True)
    sudo_exec.Popen(trim)
    sudo_shell.Popen(stream_on)
    sudo_shell.Popen(clear_trace)
    outpath = 'stream_on_discard/'
    subprocess.call('mkdir {}'.format(outpath), shell=True)
    runtest(load=True, outpath=outpath)
    runtest(loop=testloop, outpath=outpath)

    subprocess.call('rm -rdf {}/*'.format(nvme_path), shell=True)
    sudo_exec.Popen(trim)
    sudo_shell.Popen(stream_off)
    sudo_shell.Popen(clear_trace)
    outpath = 'stream_off_discard/'
    subprocess.call('mkdir {}'.format(outpath), shell=True)
    runtest(load=True, outpath=outpath)
    runtest(loop=testloop, outpath=outpath)

    umount()

    mount(discard='')
    subprocess.call('rm -rdf {}/*'.format(nvme_path), shell=True)
    sudo_exec.Popen(trim)
    sudo_shell.Popen(stream_on)
    sudo_shell.Popen(clear_trace)
    outpath = 'stream_on/'
    subprocess.call('mkdir {}'.format(outpath), shell=True)
    runtest(load=True, outpath=outpath)
    runtest(loop=testloop, outpath=outpath)

    subprocess.call('rm -rdf {}/*'.format(nvme_path), shell=True)
    sudo_exec.Popen(trim)
    sudo_shell.Popen(stream_off)
    sudo_shell.Popen(clear_trace)
    outpath = 'stream_off/'
    subprocess.call('mkdir {}'.format(outpath), shell=True)
    runtest(load=True, outpath=outpath)
    runtest(loop=testloop, outpath=outpath)


if __name__ == "__main__":

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-w', '--workload', help='YCSB workload')
    argparser.add_argument('-p', '--ycsbpath', help='YCSB working path')

    args = argparser.parse_args()

    main(args.workload, args.ycsbpath)
