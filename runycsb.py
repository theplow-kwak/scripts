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

sudo_passwd = getpass.getpass('password:')
keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>[\w|.]+),?')

wai_info = 'nvme hynix wai-information /dev/nvme0'.split()
cat_trace = 'cat /sys/kernel/debug/tracing/trace_pipe'.split()
ycsb_load = './bin/ycsb load rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data'.split()
ycsb_run = './bin/ycsb run rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data'.split()

#ycsb = subprocess.Popen(ycsb_load, stdin=subprocess.PIPE)
#ycsb.wait()

col_names = ['lapstime', 'cum_nand_written', 'cum_host_writes', 'cum_nand_erased', 'nand_written', 'host_writes', 'nand_erased', 'waf', 'wai']
data = pd.DataFrame(columns = col_names)

cmd1 = subprocess.Popen(['echo', sudo_passwd], stdout=subprocess.PIPE)
cmd3 = subprocess.Popen(['sudo', '-S'] + cat_trace, stdin=cmd1.stdout, stdout=subprocess.PIPE)

for i in range(100):
    cmd1 = subprocess.Popen(['echo', sudo_passwd], stdout=subprocess.PIPE)
    cmd2 = subprocess.Popen(['sudo', '-S'] + wai_info, stdin=cmd1.stdout, stdout=subprocess.PIPE)
    starttime = time.time()
    start = dict(keyval_exp.findall(str(cmd2.communicate()[0])))
    for k, v in start.items():
        start[k] = to_num(v)
    print("\n start: ", start)

    nvmeparser = subprocess.Popen('python3 /home/dhkwak/projects/traceparser/nvmeparser.py'.split(), stdin=cmd3.stdout)

    ycsb = subprocess.Popen(ycsb_run, stdin=subprocess.PIPE)
    ycsb.wait()
    time.sleep(10)
    
    nvmeparser.send_signal(signal.SIGINT)
    nvmeparser.wait()
        
    cmd1 = subprocess.Popen(['echo', sudo_passwd], stdout=subprocess.PIPE)
    cmd2 = subprocess.Popen(['sudo', '-S'] + wai_info, stdin=cmd1.stdout, stdout=subprocess.PIPE)
    end = dict(keyval_exp.findall(str(cmd2.communicate()[0])))
    endtime = time.time()
    for k, v in end.items():
        end[k] = to_num(v)
    
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
