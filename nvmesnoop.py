#!/usr/bin/python3
# @lint-avoid-python-3-compatibility-imports
#
# biosnoop  Trace block device I/O and print details including issuing PID.
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
import ctypes as ct
import time
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import threading


# load BPF program
prog = """
#include <uapi/linux/ptrace.h>
#include <linux/blkdev.h>
#include <linux/blk_types.h>
#include <linux/nvme.h>

struct val_t {
    u64 ts;
    bool admin;
    char taskid[TASK_COMM_LEN];
};

struct data_t {
    u16 opcode;
    u64 latency;
    u64 slba;
    u64 len;
    u64 ts;
    u8 stream;
    char disk_name[DISK_NAME_LEN];
    char taskid[TASK_COMM_LEN];
};

struct nvme_request {
    struct nvme_command	*cmd;
    union nvme_result	result;
    u8			retries;
    u8			flags;
    u16			status;
};

#define REQ_OP_BITS	8
#define REQ_OP_MASK	((1 << REQ_OP_BITS) - 1)
#define req_op(req) ((req)->cmd_flags & REQ_OP_MASK)

BPF_HASH(start, struct request *, struct val_t);
BPF_PERF_OUTPUT(events);

int trace_req_start(struct pt_regs *ctx, struct nvme_ns *ns, struct request *req)
{
    u64 ts;
    struct val_t val = {};

    val.ts = bpf_ktime_get_ns();
    bpf_get_current_comm(&val.taskid, sizeof(val.taskid));
    if(ns)
        val.admin = 0;
    else
        val.admin = 1;
    
    start.update(&req, &val);

    return 0;
}

int trace_req_completion(struct pt_regs *ctx, struct request *req)
{
    u64 tsp,ts;
    struct val_t *valp;
    struct data_t data = {};

    valp = start.lookup(&req);
    ts = bpf_ktime_get_ns();
    if (valp == 0) {
        // missed tracing issue
        return 0;
    }
    
    tsp = valp->ts;
    data.latency = ts - tsp;
    data.ts = tsp;
    bpf_probe_read(&data.taskid, sizeof(data.taskid), valp->taskid);
    
    if (valp->admin) {
        data.opcode = (((struct nvme_request*)(req+1))->cmd)->common.opcode | 0x100;
    } else {
        data.opcode = req->cmd_flags & REQ_OP_MASK;
        if(data.opcode == 0 || data.opcode == 1 || data.opcode == 3 || data.opcode == 9 ) {
            data.len = req->__data_len >> 9;
            data.slba = req->__sector;
            data.stream = (req->write_hint) ? (req->write_hint-1) : 0;
        }
        struct gendisk *rq_disk = req->rq_disk;
        bpf_probe_read(&data.disk_name, sizeof(data.disk_name), rq_disk->disk_name);
    }
    
    events.perf_submit(ctx, &data, sizeof(data));
    start.delete(&req);

    return 0;
}
"""


TASK_COMM_LEN = 16  # linux/sched.h
DISK_NAME_LEN = 32  # linux/genhd.h

nvme_cmd_opcode = {
    0 : 'read',
    1 : 'write',
    2 : 'flush',
    3 : 'discard',
    4 : 'ZONE_REPORT',
    5 : 'SECURE_ERASE',
    6 : 'ZONE_RESET',
    7 : 'WRITE_SAME',
    9 : 'write_zeroes',
    32: 'SCSI_IN',
    33: 'SCSI_OUT',
    34: 'DRV_IN',
    35: 'DRV_OUT',
    0x100: 'delete_sq',
    0x101: 'create_sq',
    0x102: 'get_log_page',
    0x104: 'delete_cq',
    0x105: 'create_cq',
    0x106: 'identify',
    0x108: 'abort_cmd',
    0x109: 'set_features',
    0x10a: 'get_features',
    0x10c: 'async_event',
    0x10d: 'ns_mgmt',
    0x110: 'activate_fw',
    0x111: 'download_fw',
    0x115: 'ns_attach',
    0x118: 'keep_alive',
    0x119: 'directive_send',
    0x11a: 'directive_recv',
    0x17C: 'dbbuf',
    0x180: 'format_nvm',
    0x181: 'security_send',
    0x182: 'security_recv',
    0x184: 'sanitize_nvm',
}

class Data(ct.Structure):
    _fields_ = [
        ("opcode", ct.c_int16),
        ("latency", ct.c_ulonglong),
        ("slba", ct.c_ulonglong),
        ("len", ct.c_ulonglong),
        ("ts", ct.c_ulonglong),
        ("stream", ct.c_byte),
        ("disk_name", ct.c_char * DISK_NAME_LEN),
        ("taskid", ct.c_char * TASK_COMM_LEN)
    ]


# process event
def get_event(cpu, data, size):
    event = ct.cast(data, ct.POINTER(Data)).contents

    global tag
    global count
    global outfile
    global display

    result = [round(float(event.ts) / 1000000000, 6), event.taskid.decode('UTF-8'), event.disk_name.decode('UTF-8'), nvme_cmd_opcode.get(event.opcode, hex(event.opcode & 0xff).rstrip("L")),
              event.stream, int(event.slba), int(event.len), round(float(event.latency) / 1000000000, 6)]
    count += 1
    outfile.writerow(result)

    if display & ((time.time() - tag) > 1):
        print('{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}'.format(count, *result))
        tag = time.time()


class CaptureLog(threading.Thread):

    def __init__(self, filename=None, verbose=False):
        super(CaptureLog, self).__init__()
        self.exit = threading.Event()
        self.verbose = verbose
        self.filename = filename
        self.columns = ['timestamp', 'taskid', 'nvme', 'opcode', 'stream', 'slba', 'len', 'latency']


    def run(self):
        import csv
        import os

        global tag
        global count
        global outfile
        global display

        tag = time.time()
        count = 0
        display = 0

        b = BPF(text=prog, cflags=['-w'])
        b.attach_kprobe(event="nvme_setup_cmd", fn_name="trace_req_start")
        b.attach_kprobe(event="nvme_complete_rq", fn_name="trace_req_completion")

        if self.verbose:
            display = 1
            # header
            print('{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}'.format('index', *self.columns))

        if self.filename is None:
            self.filename = "nvme" + time.strftime("-%m%d-%H%M") + ".csv"

        fout = open(self.filename, 'w')
        outfile = csv.writer(fout)
        outfile.writerow(self.columns)

        uid = os.environ.get('SUDO_UID')
        gid = os.environ.get('SUDO_GID')
        if uid is not None:
            os.chown(self.filename, int(uid), int(gid))

        # loop with callback to print_event
        b["events"].open_perf_buffer(get_event, page_cnt=1024 * 8)

        try:
            while not self.exit.is_set():
                b.perf_buffer_poll()

        except KeyboardInterrupt:
            pass

        fout.close()

    def shutdown(self):
        self.exit.set()


def Statistics(trace_datas):
    print("\n\n Operation counts and data size: \n",
          trace_datas.pivot_table(values='len', index='stream', columns=['opcode'], aggfunc=['count', 'sum'],
                                  fill_value=0))
    print("\n\n LBA describes per each stream: \n", trace_datas.groupby('stream')['slba'].describe())
    print("\n\n length describes per each stream: \n", trace_datas.groupby('stream')['len'].describe())
    print("\n\n latency describes per each stream: \n", trace_datas.groupby('stream')['latency'].describe())


def graph(chunk, ax_slba, ax_latency):

    nStreams = chunk['stream'].max() + 1

    datas = chunk[['slba', 'latency']] # .set_index(p_trace['timestamp'])
    streams = np.array(chunk['stream'])
    opcodes = chunk['opcode']


    key = 'slba'
    ax_slba.plot(datas[list(opcodes != 'write')][key], '.', color='silver', label="others")
    for n in range(nStreams):
        ax_slba.plot(datas[list(opcodes == 'write') & (streams == n)][key], '.', label="stream=%d " % (n))
        ax_slba.set_ylabel(key)

    key = 'latency'
    ax_latency.plot(datas[list(opcodes != 'write')][key], '.', color='silver', label="others")
    for n in range(nStreams):
        ax_latency.plot(datas[list(opcodes == 'write') & (streams == n)][key], '.', label="stream=%d " % (n))
        ax_latency.set_ylabel(key)

    plt.xlabel('time')
    plt.legend()
    plt.draw()
    plt.pause(1e-17)


def ViewResult(filename):

    skiprows = 0
    nrows = 100000

    dtype = {'timestamp': 'float64', 'taskid': 'category', 'nvme': 'category', 'opcode': 'category', 'stream': 'uint8',
             'slba': 'uint32', 'len': 'uint16', 'latency': 'float16'}
    start = time.time()
    # trace_datas = pd.DataFrame()
    # trace_datas = pd.read_csv(filename, header=0, dtype=dtype)
    chunks = pd.read_csv(filename, index_col=0, header=0, dtype=dtype, chunksize=1000000)
    #, skiprows= skiprows, nrows=nrows)
    print('elaps {} seconds'.format(time.time()-start))

    # Statistics(trace_datas)

    fig = plt.figure(figsize=(15, 9))
    ax_slba = plt.subplot(211)
    ax_latency = plt.subplot(212)
    fig.tight_layout()

    for chunk in chunks:
        print(chunk.head())
        graph(chunk, ax_slba, ax_latency)
    trace_datas = pd.concat([chunk])

    print(trace_datas)

    plt.show()
    return trace_datas


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--display', action='store_true', help='display the reports')
    argparser.add_argument('-o', '--outfile', help='output file')
    argparser.add_argument('-f', '--filename', help='trace data file (csv)')  # nargs='+',
    argparser.add_argument('-v', '--verbose', action='store_true', help='verbose display')
    args = argparser.parse_args()

    outfilename = "nvme" + time.strftime("-%m%d-%H%M") + ".csv"

    if args.outfile:
        outfilename = args.outfile

    if args.filename:
        ViewResult(args.filename)
    else:
        process = CaptureLog(outfilename, args.verbose)
        process.start()

        try:
            while 1:
                pass
        except KeyboardInterrupt:
            pass

        process.shutdown()
        process.join()
        if args.display:
            ViewResult([outfilename])


if __name__ == "__main__":
    main()

