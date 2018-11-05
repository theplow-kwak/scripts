#!/usr/bin/python3

import os, pwd
import argparse
import subprocess
import multiprocessing
import resource
import time
import logging

from getwai import *
from nvmesnoop import *

class testWorker(multiprocessing.Process):

    def __init__(self, name, script, cwd='./'):
        super().__init__()
        self.script = script.split()
        self.filename = name + '.log'
        self.cwd = cwd

    def drop_privileges(self):
        if os.getuid() != 0:
            # We're not root so, like, whatever dude
            return

        # Get the uid/gid from the name
        user_name = os.getenv("SUDO_USER")
        pwnam = pwd.getpwnam(user_name)

        # Try setting the new uid/gid
        os.setgid(pwnam.pw_gid)
        os.setuid(pwnam.pw_uid)

    def run(self):
        self.drop_privileges()

        # start ycsb script
        logfile = open(self.filename, "w")
        p_ycsb = subprocess.Popen(self.script, stdout=subprocess.PIPE, universal_newlines=True,
                                cwd=self.cwd)

        try:
            while p_ycsb.poll() is None:
                logdata = p_ycsb.stdout.readline()
                print(logdata.strip())
                logfile.write(logdata)
        except KeyboardInterrupt:
            p_ycsb.terminate()
            pass

        p_ycsb.wait()

def set_open_file_limit_up_to(limit=65536):

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    #limit = max(soft, limit)
    #limit = max(limit, hard)
    print(limit, soft)
    while limit > soft:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (limit, limit))
            break
        except ValueError:
            limit -= 256
            print('value error. reset limit to {}'.format(limit))
        except:
            print('unexpected exception')

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    print('open file limit set to %d:%d'% (soft, hard))
    return (soft, hard)

def bm_test(name, script, nvme='/dev/nvme0', verbose='s', cwd='./'):

    nvmesnoop = CaptureNvme(filename=name+'.nvme.csv', verbose=verbose)
    wai_info = CaptureWai(nvme, filename=name+'.wai.csv', verbose=verbose)

    nvmesnoop.start()
    wai_info.start()

    set_open_file_limit_up_to()

    try:
        p = testWorker(name, script)
        p.start()
        p.join()
    except KeyboardInterrupt:
        pass

    time.sleep(10)
    nvmesnoop.shutdown()
    wai_info.shutdown()
    nvmesnoop.join()
    wai_info.join()

    nvmesnoop.summary()
    wai_info.summary()



#script = ''
#ycsb_workload = 'workloads/nvme_test'
#ycsb_load = './bin/ycsb load rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data'.format(ycsb_workload, target_path)
#ycsb_run = './bin/ycsb run rocksdb -s -P {0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(ycsb_workload, target_path)

stream_on = ['sudo', 'sh', '-c', 'echo 1 > /sys/module/nvme_core/parameters/streams']
stream_off = ['sudo', 'sh', '-c', 'echo 0 > /sys/module/nvme_core/parameters/streams']
trim = 'fstrim -v {}'.format(nvme_path).split()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-n', '--nvme', help='nvme device name')
    argparser.add_argument('-t', '--title', help='Title - output file name')
    argparser.add_argument('-w', '--workload', help='ycsb workload')
    argparser.add_argument('-p', '--path', help='target path')
    argparser.add_argument('-s', '--script', help='test script')
    argparser.add_argument('-v', '--verbose', nargs='?', default='s', help='verbose display')
    args = argparser.parse_args()

    #    subprocess.Popen(stream_on, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    nvme_dev = None

    if args.path:
        target_path = args.path
    else:
        target_path = '/mnt/gemini'

    if args.nvme:
        nvme_dev = args.nvme

    if nvme_dev is None:
        out = subprocess.Popen('df {}'.format(target_path).split(), stdout=subprocess.PIPE).communicate()
        m = re.search(r'(/[^\s]+)\s', str(out))
        if m:
            nvme_dev = m.group(1)
        else:
            nvme_dev = '/dev/nvme0'

    if args.title:
        title = args.title
    else:
        title = 'workloadf'

    if args.script:
        script = args.script
    else:
        script = './bin/ycsb run rocksdb -s -P workloads/{0} -p rocksdb.dir={1}/ycsb-rocksdb-data -threads 32'.format(title, target_path)

    bm_test(name=title, script=script, nvme=nvme_dev, verbose=args.verbose)


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



