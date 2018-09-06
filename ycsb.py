#!/usr/bin/python3

from getwai import *
import os
import argparse
import subprocess
import threading
import signal
import time


script = ''
nvme_path = '/mnt/nvme'
ycsb_workload = 'workloads/workloada'
ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, nvme_path).split()
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path).split()

ycsb = subprocess.Popen(ycsb_load, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd='../ycsb')

while ycsb.poll() is None:
    logdata = ycsb.stdout.readline()
    print(logdata.strip())

ycsb.wait()

def run_script(outfile, script):
    # start nvmesnoop
    sudo_exec = SudoProcess()
    nvme = sudo_exec.Popen('./nvmesnoop.py -o {}.nvme.csv'.format(outfile).split(), wait=False)

    # start getwai
    wai_info = WaiInfo()
    stop_threads = False
    tmp = threading.Thread(target=capture_wai, args=(wai_info, outfile+'.wai.csv', False, lambda: stop_threads))
    tmp.start()

    # start ycsb script
    file = open(outfile+'.log', "w")
    ycsb = subprocess.Popen(script, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd='../ycsb')

    while ycsb.poll() is None:
        logdata = ycsb.stdout.readline()
        print(logdata.strip())
        file.write(logdata)

    ycsb.wait()
    stop_threads = True
    time.sleep(10)
    # nvme.terminate()
    # send_signal(signal.SIGINT)

run_script('workloada', ycsb_run)

ycsb_workload = 'workloads/workloadb'
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path).split()
run_script('workloadb', ycsb_run)

ycsb_workload = 'workloads/workloadf'
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path).split()
run_script('workloadf', ycsb_run)

ycsb_workload = 'workloads/nvme_test'
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path).split()
run_script('nvme_test', ycsb_run)



