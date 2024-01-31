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


def main(workload, ycsbpath):
    sudo_shell = SudoProcess(True)
    sudo_shell.Popen(nvme_enable)
    sudo_shell.Popen(trace_on)
    sudo_exec = SudoProcess()

    testloop = 6
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


if __name__ == "__main__":

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-w', '--workload', help='YCSB workload')
    argparser.add_argument('-p', '--ycsbpath', help='YCSB working path')

    args = argparser.parse_args()

    main(args.workload, args.ycsbpath)
