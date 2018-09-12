#!/usr/bin/python3

from getwai import *
import os, pwd
import argparse
import subprocess
import threading
from multiprocessing import Process
import signal
import time


script = ''
nvme_path = '/mnt/gemini'
ycsb_workload = 'workloads/nvme_test'
ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, nvme_path)
ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, nvme_path)

stream_on = ['sudo', 'sh', '-c', 'echo 1 > /sys/module/nvme_core/parameters/streams']
stream_off = ['sudo', 'sh', '-c', 'echo 0 > /sys/module/nvme_core/parameters/streams']


def ycsbload(name, script):
    drop_privileges()
    ycsb = subprocess.Popen(ycsb_load.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, cwd='../ycsb')

    while ycsb.poll() is None:
        logdata = ycsb.stdout.readline()
        print(logdata.strip())

    ycsb.wait()


def drop_privileges():
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    user_name = os.getenv("SUDO_USER")
    pwnam = pwd.getpwnam(user_name)

    # Remove group privileges
    #os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(pwnam.pw_gid)
    os.setuid(pwnam.pw_uid)

    #Ensure a reasonable umask
    #old_umask = os.umask(0o22)

def info(title):
    print(title)
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())
    print(os.getresuid())
    print()

def start(name, script):
    drop_privileges()

    # start ycsb script
    file = open(name + '.log', "w")
    ycsb = subprocess.Popen(script.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                            cwd='../ycsb')
    info('ycsb:')

    while ycsb.poll() is None:
        logdata = ycsb.stdout.readline()
        print(logdata.strip())
        file.write(logdata)

    ycsb.wait()


def run_script(name, script):
    # start nvmesnoop
    # sudo_exec = SudoProcess()
    nvme = subprocess.Popen('./nvmesnoop.py -o {}.nvme.csv'.format(name).split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)  # , preexec_fn=os.setpgrp
    info('nvmesnoop:')
    print(nvme.pid, os.getpgid(nvme.pid))

    # start getwai
    wai_info = WaiInfo()
    stop_threads = False
    tmp = threading.Thread(target=capture_wai, args=(wai_info, name+'.wai.csv', False, lambda: stop_threads))
    tmp.start()

#    subprocess.Popen(stream_on, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p = Process(target=start, args=(name, script))
    p.start()
    p.join()

    stop_threads = True
    info('end of script:')
    time.sleep(10)
    nvme.send_signal(signal.SIGINT)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-n', '--nvme', help='nvme device name')
    argparser.add_argument('-t', '--title', help='Title - output file name')
    argparser.add_argument('-s', '--script', help='test script')
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose display')
    args = argparser.parse_args()

    run_script(args.title, args.script)

if __name__ == "__main__":

    main()

#p = Process(target=ycsbload, args=('load', ycsb_load))
#p.start()
#p.join()


#ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format('workloads/workloadx', nvme_path)
#run_script('load', ycsb_load)

#subprocess.Popen(stream_on, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/workloadx', nvme_path)
#run_script('workloadx_on', ycsb_run)

#subprocess.Popen(stream_off, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/workloadx', nvme_path)
#run_script('workloadx_off', ycsb_run)

#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/workloadf', nvme_path)
#run_script('workloadf', ycsb_run)

#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/nvme_test', nvme_path)
#run_script('nvme_test', ycsb_run)



