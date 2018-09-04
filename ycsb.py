#!/usr/bin/python3

from getwai import *
import os
import argparse
import subprocess
import threading
import signal
import time

outfile = 'rocksdb'
script = ''
nvme_path = '/mnt/nvme'
ycsb_workload = 'workloads/workloadx'
ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, nvme_path).split()
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path).split()

ycsb = subprocess.Popen(ycsb_load, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd='../ycsb')

while ycsb.poll() is None:
    logdata = ycsb.stdout.readline()
    print(logdata.strip())

ycsb.wait()

sudo_exec = SudoProcess()
wai_info = WaiInfo()
nvme = sudo_exec.Popen('./nvmesnoop.py -o {}.nvme.csv'.format(outfile).split(), wait=False)

stop_threads = False
tmp = threading.Thread(target=capture_wai, args=(wai_info, outfile+'.wai.csv', False, lambda: stop_threads))
tmp.start()

file = open(outfile+'.log', "w")

ycsb = subprocess.Popen(ycsb_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd='../ycsb')

while ycsb.poll() is None:
    logdata = ycsb.stdout.readline()
    print(logdata.strip())
    file.write(logdata)

ycsb.wait()
stop_threads = True
time.sleep(10)

nvme.terminate()
# send_signal(signal.SIGINT)

