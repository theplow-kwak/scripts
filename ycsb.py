#!/usr/bin/python3

from getwai import *
from nvmesnoop import *
import os, pwd
import argparse
import subprocess
import threading
from multiprocessing import Process
import signal
import time


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


def run_script(name, script):
    drop_privileges()

    # start ycsb script
    file = open(name + '.log', "w")
    pycsb = subprocess.Popen(script.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                            cwd='../ycsb')

    while pycsb.poll() is None:
        logdata = pycsb.stdout.readline()
        print(logdata.strip())
        file.write(logdata)

    pycsb.wait()


def bm_test(name, script, nvme='/dev/nvme0'):
    # start nvmesnoop
    nvmesnoop = CaptureLog(name+'.nvme.csv', False)
    nvmesnoop.start()

    # start getwai
    wai_info = CaptureWai(nvme, name+'.wai.csv', False)
    wai_info.start()

    p = Process(target=run_script, args=(name, script))
    p.start()
    p.join()

    wai_info.shutdown()
    wai_info.join()
    time.sleep(5)
    nvmesnoop.shutdown()
    nvmesnoop.join()


#script = ''
#ycsb_workload = 'workloads/nvme_test'
#ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, target_path)
#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, target_path)

stream_on = ['sudo', 'sh', '-c', 'echo 1 > /sys/module/nvme_core/parameters/streams']
stream_off = ['sudo', 'sh', '-c', 'echo 0 > /sys/module/nvme_core/parameters/streams']


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-n', '--nvme', help='nvme device name')
    argparser.add_argument('-t', '--title', help='Title - output file name')
    argparser.add_argument('-p', '--path', help='target path')
    argparser.add_argument('-s', '--script', help='test script')
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose display')
    args = argparser.parse_args()

    #    subprocess.Popen(stream_on, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    target_path = '/mnt/gemini'
    if args.path:
        target_path = args.path

    nvme_dev = '/dev/nvme0'
    out = subprocess.Popen('df {}'.format(target_path).split(), stdout=subprocess.PIPE).communicate()
    m = re.search(r'(/[^\s]+)\s', str(out))
    if m:
        nvme_dev = m.group(1)

    if args.title:
        title = args.title
    else:
        title = 'workloadf'

    if args.script:
        ycsb_run = args.script
    else:
        ycsb_run = './bin/ycsb run rocksdb -s -P workloads/{0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(title, target_path)

    bm_test(title, ycsb_run, nvme_dev)



if __name__ == "__main__":

    main()

#p = Process(target=ycsbload, args=('load', ycsb_load))
#p.start()
#p.join()


#ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format('workloads/workloadx', nvme_path)
#run_script('load', ycsb_load)

#subprocess.Popen(stream_on, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

#subprocess.Popen(stream_off, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/workloadx', nvme_path)
#run_script('workloadx_off', ycsb_run)

#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/workloadf', nvme_path)
#run_script('workloadf', ycsb_run)

#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format('workloads/nvme_test', nvme_path)
#run_script('nvme_test', ycsb_run)



