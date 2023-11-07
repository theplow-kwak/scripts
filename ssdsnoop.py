#!/usr/bin/python3
# @lint-avoid-python-3-compatibility-imports
#
# ssdsnoop  Trace block device I/O and print details including issuing PID.
#       For Linux, uses BCC, eBPF.
#
# This uses in-kernel eBPF maps to cache process details (PID and comm) by I/O
# request, as well as a starting timestamp for calculating I/O latency.
#
# Copyright (c) 2015 Brendan Gregg.
# Licensed under the Apache License, Version 2.0 (the "License")
#
# 16-Sep-2015   Brendan Gregg   Created this.
# 11-Feb-2016   Allan McAleavy  updated for BPF_PERF_OUTPUT


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from bcc import BPF
from datetime import date, datetime
import ctypes as ct
import time
import argparse
import os
import io
import csv
import re 
import json


TASK_COMM_LEN = 16  # linux/sched.h
DISK_NAME_LEN = 32  # linux/genhd.h

cmd_opcode = {
    0: 'read',
    1: 'write',
    2: 'flush',
    3: 'discard',
    4: 'ZONE_REPORT',
    5: 'SECURE_ERASE',
    6: 'ZONE_RESET',
    7: 'WRITE_SAME',
    9: 'write_zeroes',
    32: 'SCSI_IN',
    33: 'SCSI_OUT',
    34: 'DRV_IN',
    35: 'DRV_OUT',
}


class Data(ct.Structure):
    _fields_ = [
        ("io_start_time_ns", ct.c_ulonglong),
        ("taskid", ct.c_char * TASK_COMM_LEN),
        ("disk_name", ct.c_char * DISK_NAME_LEN),
        ("opcode", ct.c_uint8),
        ("cmnd", ct.c_uint8),
        ("slba", ct.c_ulonglong),
        ("len", ct.c_ulong),
        ("latency_ns", ct.c_longlong),
        ("major", ct.c_uint16),
        ("minor", ct.c_uint16),        
        ("ata_cmd", ct.c_uint8),
    ]


class NestedDict(dict):
    def __missing__(self, key):
        return super(NestedDict, self).setdefault(key, NestedDict())


class CollectsWorkload:
    def __init__(self, interval=1.0, initialTime=0.0, fd=0, verbose=''):
        self.TimeInterval = interval
        self.TimeTag = initialTime
        self.LastTimeTag = initialTime
        self.data = NestedDict()
        self.total = NestedDict()
        self.fd = fd
        self.verbose = verbose

    def saveStatistics(self, ts):
        if 't' in self.verbose or 's' in self.verbose:
            print(str(ts)+': '+str(self.data))
        if self.fd:
            self.fd.write(str(ts)+': '+str(self.data)+'\n')
        self.data.clear()
        print(json.dumps(self.data, ensure_ascii=False, indent="\t") )

    def update(self, ts, disk, cmd, slen):
        if self.TimeTag == 0.0:
            self.TimeTag = ts
        if ((ts - self.TimeTag) > self.TimeInterval):
            self.saveStatistics(self.LastTimeTag)
            self.TimeTag = ts
        self.LastTimeTag = ts
        slen = int(slen)
        try:
            self.data[disk][cmd][slen] += 1
        except:
            self.data[disk][cmd][slen] = 1
        try:
            self.total[disk][cmd][slen] += 1
        except:
            self.total[disk][cmd][slen] = 1
       
    def setFile(self, fd):
        self.fd = fd

    def get(self):
        return self.total

    def close(self):
        self.saveStatistics(self.LastTimeTag)
        if 't' in self.verbose or 's' in self.verbose:
            print(str("total")+', '+str(self.total))
        if self.fd:
            self.fd.write(str("\ntotal")+', '+str(self.total)+'\n')


class devFilter():
    def __init__(self, filters='*'):
        self.filters = None
        self.setfilter(filters)
        
    def setfilter(self, filters='*'):
        if filters is not None:
            self.filters = list(map(lambda v: re.compile(v.replace('*', '.*')), filters))

    def match(self, key):
        if self.filters is not None:
#            x = list(filter((lambda f: f.match(key)), self.filters))
            m = [ key for x in self.filters if x.match(key) ]
            return len(m)
        else:
            return True


class logInfo():
    # 't' - test mode, display on consol with 1 sec interval
    # 'c' - display on consol
    # 'f' - save data to file
    def __init__(self, format=None, verbose=False, interval=None):
        self.count = 0
        self.logformat = format
        self.verboseType = None
        self.set(verbose, interval) 

    def set(self, verbose=None, interval=None):
        self.interval(interval)
        self.verbose(verbose) 

    def verbose(self, verbose=None):
        if 't' in verbose or 'a' in verbose:
            self.verboseType = verbose
            if 'a' in verbose:
                self.interval(0.0)
                
    def interval(self, interval=None):
        if interval is not None:
            self.verboseTimeTag = time.time()
            self.verboseTimeInterval = interval

    def format(self, format=None):
        self.logformat = format

    def display(self, header=None, data=None):
        if self.verboseType:
            print(header, self.logformat.format(**data))
        
    def log(self, data=None):
        self.count += 1
        __current_ts = time.time()
        if ((__current_ts - self.verboseTimeTag) > self.verboseTimeInterval):
            self.display(header='{:d}\t'.format(self.count), data=data)
            self.verboseTimeTag = __current_ts

            

class CaptureSSD:
    interval = 1
    logformat = '{ts:>18.6f} {taskid:^16s} {major:>3d}:{minor:<3d} {disk:^10s} {opcode:^10s} {cmnd:^7x} {slba:>14d} {len:>7d} {latency:>14.3f} {ata_cmd:^7x}'
    fieldnames = ['ts', 'taskid', 'major', 'minor', 'disk', 'opcode', 'cmnd', 'slba', 'len', 'latency', 'ata_cmd']
    header = ['TimeStamp', 'TaskID', 'Major', 'Minor', 'Disk', 'Opcode', 'cmnd', 'slba', 'len', 'Latency', 'ata_cmd']
    pagecount=2048 * 64

    def __init__(self, dev=None, filename=None, verbose='f', interval=1):
        self.count = 0
        self.start_ts = 0
        self.diskfilter = devFilter('*')
        self.filename = filename
        self.f_ext_no = 0
        self.verbose = verbose
        self.log = logInfo(self.logformat, verbose, interval)
        self.CmdCounter = CollectsWorkload(interval=interval, verbose=verbose)
        self.start_time = time.time()
        self.today = date.today()
        self.bcc = BPF(src_file="bpf_prog_kprobe.c", cflags=['-w','-O3', '-I'+os.path.split(os.path.realpath(__file__))[0], '-include', 'asm_goto_workaround.h'])

    def fileopen(self):
        if not 'f' in self.verbose:
            return 
            
        if self.filename is None:
            self.filename = 'ssd'

        self.count = 0
        
        while True:
            self.WorkloadFileName = '{}-{:%Y%m%d}_{}-workload.csv'.format(self.filename, self.today, self.f_ext_no)
            if not os.path.exists(self.WorkloadFileName): break
            self.f_ext_no += 1
            continue

        self.StatisticFileName = '{}-{:%Y%m%d}_{}-statistics.csv'.format(self.filename, self.today, self.f_ext_no)
        self.__workload_fd = io.open(self.WorkloadFileName, 'w', encoding='utf-8')
        self.workloadfile = csv.writer(self.__workload_fd, quoting=csv.QUOTE_NONNUMERIC)
        self.__statistic_fd = io.open(self.StatisticFileName, 'w', encoding='utf-8')
        self.statisticfile = csv.writer(self.__statistic_fd, quoting=csv.QUOTE_NONNUMERIC)

        #__uid = os.environ.get('SUDO_UID')
        #__gid = os.environ.get('SUDO_GID')
        #if __uid is not None:
        #    os.chown(self.WorkloadFileName, int(__uid), int(__gid))
        #    os.chown(self.StatisticFileName, int(__uid), int(__gid))
        self.workloadfile.writerow(self.header)
        self.CmdCounter.setFile(self.__statistic_fd)
       
    def start(self):
        # loop with callback to print_event
        self.fileopen()

        if BPF.get_kprobe_functions(b'blk_start_request'):
            self.bcc.attach_kprobe(event="blk_start_request", fn_name="blk_req_start")
        self.bcc.attach_kprobe(event="blk_mq_start_request", fn_name="blk_req_start")
        self.bcc.attach_kprobe(event="blk_update_request", fn_name="blk_req_completion")

        self.bcc["events"].open_perf_buffer(self.get_event, page_cnt=self.pagecount)

        while 1:
            try:
                self.bcc.kprobe_poll(1000)
                if date.today() > self.today:
                    self.CmdCounter.close()
                    self.__workload_fd.close()
                    self.__statistic_fd.close()
                    self.today = date.today()
                    self.f_ext_no = 0
                    self.fileopen()
                if self.count > 25000000:
                    self.CmdCounter.close()
                    self.__workload_fd.close()
                    self.__statistic_fd.close()
                    self.f_ext_no += 1
                    self.fileopen()
                    
            except KeyboardInterrupt:
                break

        try:
            self.CmdCounter.close()
            self.__workload_fd.close()
            self.__statistic_fd.close()
        except:
            pass

    # process event
    def get_event(self, cpu, data, size):
        self.event = ct.cast(data, ct.POINTER(Data)).contents

        if self.start_ts == 0:
            self.start_ts = self.event.io_start_time_ns
            self.current_ts = 0.0

        self.current_ts = (self.event.io_start_time_ns - self.start_ts) / 1000000000
        # self.current_time = int(datetime.fromtimestamp(self.current_ts+self.start_time).strftime("%Y%m%d%H%M%S%f"))
        self.current_time = self.current_ts+self.start_time
        self.__values = [self.current_time, self.event.taskid.decode('utf-8'),
                       self.event.major, self.event.minor, self.event.disk_name.decode('utf-8'),
                       str(cmd_opcode.get(self.event.opcode, (self.event.opcode & 0xff))), self.event.cmnd,
                       self.event.slba, self.event.len, (self.event.latency_ns / 1000), self.event.ata_cmd]
        self.result = dict(zip(self.fieldnames, self.__values))

        if not self.diskfilter.match(str(self.result['disk'])):
            return 
            
        if 'f' in self.verbose:
            try:
                self.workloadfile.writerow(self.__values)
            except:
                pass
        if self.__values[9] > 10000000:
            print("error!! ", self.count, self.event.io_start_time_ns, self.start_ts, self.current_ts, self.event.latency_ns, self.__values[9])  
		   
        self.count += 1
        self.CmdCounter.update(self.result['ts'], self.result['disk'], self.result['opcode']+"_"+str(self.result['cmnd']), self.result['len'])
        self.log.log(self.result)

    def summary(self):
        print()
        print('Total operation count: ', self.count)

    def setDiskFilter(self, filters):
        self.diskfilter.setfilter(filters)


def readWorkloadFile(filename, verbose='f', interval=1, filters='*', outfile=None):
    workloadFile = open(filename, 'r')
    csvReader = csv.reader(workloadFile, quoting=csv.QUOTE_NONNUMERIC)
    outfile = 'statistics' if outfile is None else 'statistics.' + str(outfile)
    statisticFile = open(filename.replace('workload', outfile), 'w')
    header = csvReader.next()
    CmdCounter = CollectsWorkload(interval=interval, verbose=verbose, fd=statisticFile)
    logformat = '{ts:>14.6f} {taskid:^16s} {major:>3}:{minor:<3} {disk:^10s} {opcode:^10s} {cmnd:^7} {slba:>14} {len:>7} {latency:>14.3f} {ata_cmd:^7x}'
    fieldnames = ['ts', 'taskid', 'major', 'minor', 'disk', 'opcode', 'cmnd', 'slba', 'len', 'latency', 'ata_cmd']
    diskfilter = devFilter(filters)
    log = logInfo(logformat, verbose, interval)

    for row in csvReader:
        result = dict(zip(fieldnames, row))

        if diskfilter.match(result['disk']):
            CmdCounter.update(result['ts'], result['disk'], (result['opcode'], result['cmnd']), result['len'])
            log.log(result)
    CmdCounter.close()    


class UpdateFilter(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, map(lambda v: re.compile(v.replace('*', '.*')), values))


def main():
    verbose_opt = ['a', 't', 'f', 'c']
    argparser = argparse.ArgumentParser(description="Collects the workload of the block device.")
    argparser.add_argument('-o', '--outfile', help='set the output file name')
    argparser.add_argument('-i', '--interval', default=1, type=float, help='set the verbose interval time(seconds)')
    argparser.add_argument('-v', '--verbose', type=str, default='f', choices=['a','t','f','c'], help='set the verbose display option')
    argparser.add_argument('-f', '--diskfilter', nargs='+', type=str, help='set the disk filter')
    argparser.add_argument('-w', '--workloadfile', help='make statistics from workload file')
    argparser.add_argument('-p', '--pagecount', type=int, help='set the page counts (buffer memory)')
    args = argparser.parse_args()

    outfilename = None

    if args.workloadfile:
        readWorkloadFile(args.workloadfile, verbose=args.verbose, interval=args.interval, filters=args.diskfilter, outfile=args.outfile)
        exit()

    if args.outfile:
        outfilename = args.outfile

    ssdsnoop = CaptureSSD(filename=outfilename, verbose=args.verbose, interval=args.interval)
    if args.pagecount:
        ssdsnoop.pagecount = args.pagecount
    if args.diskfilter:
        ssdsnoop.setDiskFilter(args.diskfilter)
    ssdsnoop.start()

    ssdsnoop.summary()


if __name__ == "__main__":
    main()
