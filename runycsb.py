#!/usr/bin/python3

import re
import subprocess
import signal
import time
import getpass
import pandas as pd

def to_num(str_num):
    try:
        return float(str_num) if '.' in str_num else int(str_num, 0)
    except:
        return str_num

keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

sudo_passwd = getpass.getpass('password:')

nvme_enable = 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
trace_on = 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
clear_trace = 'echo 1 > /sys/kernel/debug/tracing/trace'
stream_on = 'echo 1 > /sys/module/nvme_core/parameters/streams'
stream_off =  'echo 0 > /sys/module/nvme_core/parameters/streams'

cat_trace = 'cat /sys/kernel/debug/tracing/trace_pipe'.split()
wai_info = 'nvme hynix wai-information /dev/nvme0'.split()

def sudo_exec(commands):
    print(commands)
    echo = subprocess.Popen(['echo', sudo_passwd], stdout=subprocess.PIPE)
    cmd = subprocess.Popen(commands, stdin=echo.stdout, stdout=subprocess.PIPE)
    return cmd

ycsb_load = './bin/ycsb load rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data'.split()
ycsb_run = './bin/ycsb run rocksdb -s -P workloads/workloada -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data'.split()

def get_wai():
    cmd1 = subprocess.Popen(['echo', sudo_passwd], stdout=subprocess.PIPE)
    cmd2 = subprocess.Popen(['sudo', '-S'] + wai_info, stdin=cmd1.stdout, stdout=subprocess.PIPE)
    _data = dict(keyval_exp.findall(str(cmd2.communicate()[0])))
    for k, v in _data.items():
        _data[k] = to_num(v)
    return _data

col_names = ['lapstime', 'cum_nand_written', 'cum_host_writes', 'cum_nand_erased', 'nand_written', 'host_writes', 'nand_erased', 'waf', 'wai']
data = pd.DataFrame(columns = col_names)

sudo_exec(['sudo', '-S', 'sh', '-c', nvme_enable])
sudo_exec(['sudo', '-S', 'sh', '-c', stream_on])
sudo_exec(['sudo', '-S', 'sh', '-c', trace_on])
sudo_exec(['sudo', '-S', 'sh', '-c', clear_trace])

cattrace = sudo_exec(['sudo', '-S'] + cat_trace)

for i in range(100):
    starttime = time.time()
    start = get_wai()
    print("\n start: ", start)

    nvmeparser = subprocess.Popen('python3 /home/dhkwak/projects/traceparser/nvmeparser.py'.split(), stdin=cattrace.stdout)

    ycsb = subprocess.Popen(ycsb_run, stdin=subprocess.PIPE)
    ycsb.wait()
    time.sleep(10)
    
    nvmeparser.send_signal(signal.SIGINT)
    nvmeparser.wait()
        
    end = get_wai()
    endtime = time.time()
    
    lapstime = endtime - starttime
    nand_written = (end['nand_written'] - start['nand_written'])
    host_writes = (end['host_writes'] - start['host_writes'])
    nand_erased = (end['nand_erased'] - start['nand_erased'])
    waf = nand_written / host_writes
    wai = nand_erased / host_writes
    data.loc[len(data)] = [lapstime, start['nand_written'], start['host_writes'], start['nand_erased'], nand_written, host_writes, nand_erased, waf, wai]
    data.to_csv('waf_info.csv')
        
    print("end: ", end)
    print("\n\n", "loop ", i)
    print("written information: ", nand_written, host_writes, nand_erased)
    print("WAF = ", waf)
    print("WAI = ", wai)
    print("\n\n")

print(data)
