#!/usr/bin/python
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

# import matplotlib.pyplot as plt
import threading


# load BPF program
prog = """
#include <uapi/linux/ptrace.h>
#include <linux/blkdev.h>
#include <linux/blk_types.h>
#include <linux/nvme.h>

struct val_t {
    bool isAdminCmd;
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
    u64 start_time_ns;
    u64 io_start_time_ns;    
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

    if(ns)
        val.isAdminCmd = 0;
    else
        val.isAdminCmd = 1;
    
    FILTER_ADMIN
    
    bpf_get_current_comm(&val.taskid, sizeof(val.taskid));
    start.update(&req, &val);

    return 0;
}

int trace_req_completion(struct pt_regs *ctx, struct request *req)
{
    u64 tsp,ts;
    bool isAdminCmd;
    u16 opcode;
    struct val_t *valp;
    struct data_t data = {};

    valp = start.lookup(&req);
    if (valp == 0) {
        // missed tracing issue
        return 0;
    }
    
    tsp = req->io_start_time_ns;
    isAdminCmd = valp->isAdminCmd;
    bpf_probe_read(&data.taskid, sizeof(data.taskid), valp->taskid);
    start.delete(&req);
    
    if (isAdminCmd) {
        data.opcode = (((struct nvme_request*)(req+1))->cmd)->common.opcode | 0x100;
    } else {
        struct gendisk *rq_disk = req->rq_disk;
        bpf_probe_read(&data.disk_name, sizeof(data.disk_name), rq_disk->disk_name);       
        FILTER_NVME
        
        opcode = data.opcode = req->cmd_flags & REQ_OP_MASK;
        FILTER_OPCODE
        
        if(opcode == 0 || opcode == 1 || opcode == 3 || opcode == 9 ) 
        {
            data.len = req->__data_len >> 9;
            data.slba = req->__sector;
            data.stream = (req->write_hint) ? (req->write_hint-1) : 0;
        }
    }
    
    data.stream = (((struct nvme_request*)(req+1))->cmd)->common.opcode;
    ts = bpf_ktime_get_ns();
    data.latency = ts - tsp;
    data.ts = tsp;
    data.start_time_ns = req->start_time_ns;
    data.io_start_time_ns = req->io_start_time_ns;
    
    events.perf_submit(ctx, &data, sizeof(data));

    return 0;
}
"""


TASK_COMM_LEN = 16  # linux/sched.h
DISK_NAME_LEN = 32  # linux/genhd.h

nvme_cmd_opcode = {
    0: "read",
    1: "write",
    2: "flush",
    3: "discard",
    4: "ZONE_REPORT",
    5: "SECURE_ERASE",
    6: "ZONE_RESET",
    7: "WRITE_SAME",
    9: "write_zeroes",
    32: "SCSI_IN",
    33: "SCSI_OUT",
    34: "DRV_IN",
    35: "DRV_OUT",
    0x100: "delete_sq",
    0x101: "create_sq",
    0x102: "get_log_page",
    0x104: "delete_cq",
    0x105: "create_cq",
    0x106: "identify",
    0x108: "abort_cmd",
    0x109: "set_features",
    0x10A: "get_features",
    0x10C: "async_event",
    0x10D: "ns_mgmt",
    0x110: "activate_fw",
    0x111: "download_fw",
    0x115: "ns_attach",
    0x118: "keep_alive",
    0x119: "directive_send",
    0x11A: "directive_recv",
    0x17C: "dbbuf",
    0x180: "format_nvm",
    0x181: "security_send",
    0x182: "security_recv",
    0x184: "sanitize_nvm",
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
        ("taskid", ct.c_char * TASK_COMM_LEN),
        ("start_time_ns", ct.c_ulonglong),
        ("io_start_time_ns", ct.c_ulonglong),
    ]


class StreamInfo:

    def __init__(self, streams):
        self.streams = np.zeros((streams + 1, 2))

    def add(self, stream, length):
        self.streams[stream] += [1, length]

    def total(self):
        return np.sum(self.streams[:, 0]), np.sum(self.streams[:, 1])

    def summary(self):
        return self.streams.tolist()


from bmcore import *


class CaptureNvme(CaptureThread):
    name = "nvme"
    interval = 1
    logformat = "{:>8} {:<20} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}"
    header = ["index", "timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"]
    nvmedata = RingBuffer(200000)

    def __init__(self, dev=None, filename=None, verbose="t"):
        super(CaptureNvme, self).__init__(filename, verbose)
        self.count = 0

        self.streaminfo = StreamInfo(8)

        global prog
        prog = prog.replace("FILTER_ADMIN", "")
        if dev is not None:
            prog = prog.replace("FILTER_NVME", "{}".format(dev))
        else:
            prog = prog.replace("FILTER_NVME", "")
        prog = prog.replace("FILTER_OPCODE", "")

        self.bcc = BPF(text=prog, cflags=["-w"])
        self.bcc.attach_kprobe(event="nvme_setup_cmd", fn_name="trace_req_start")
        self.bcc.attach_kprobe(event="nvme_complete_rq", fn_name="trace_req_completion")

    def run(self):
        # loop with callback to print_event
        self.bcc["events"].open_perf_buffer(self.get_event, page_cnt=4096 * 64)
        super(CaptureNvme, self).run()

    # process event
    def get_event(self, cpu, data, size):
        event = ct.cast(data, ct.POINTER(Data)).contents

        self.result = [
            round(float(event.ts) / 1000000000, 6),
            event.taskid.decode("UTF-8"),
            event.disk_name.decode("UTF-8"),
            nvme_cmd_opcode.get(event.opcode, hex(event.opcode & 0xFF).rstrip("L")),
            event.stream,
            int(event.slba),
            int(event.len),
            round(float(event.latency) / 1000000000, 6),
        ]
        self.count += 1
        # self.nvmedata.append(self.result)
        self.logging([self.count] + self.result)

        if nvme_cmd_opcode.get(event.opcode) is "write":
            self.streaminfo.add(event.stream, event.len)

    def work(self):
        self.bcc.perf_buffer_poll(1000)

    def summary(self):
        print()
        print("Total operation count: ", self.count)
        print(" Write count: {}, written data: {}".format(*self.streaminfo.total()))
        info = self.streaminfo.summary()
        for n in range(len(info)):
            print(" stream {} counts {} written {}".format(n, info[n][0], info[n][1]))

    def getdata(self):
        return self.nvmedata.get()


def Statistics(trace_datas):
    print("\n\n Operation counts and data size: \n", trace_datas.pivot_table(values="len", index="stream", columns=["opcode"], aggfunc=["count", "sum"], fill_value=0))
    print("\n\n LBA describes per each stream: \n", trace_datas.groupby("stream")["slba"].describe())
    print("\n\n length describes per each stream: \n", trace_datas.groupby("stream")["len"].describe())
    print("\n\n latency describes per each stream: \n", trace_datas.groupby("stream")["latency"].describe())


def graph(chunk, ax_slba, ax_latency):

    nStreams = chunk["stream"].max() + 1

    datas = chunk[["slba", "latency"]]  # .set_index(p_trace['timestamp'])
    streams = np.array(chunk["stream"])
    opcodes = chunk["opcode"]

    ax_slba.clear()
    key = "slba"
    # ax_slba.plot(datas[list(opcodes != 'write')][key], '.', color='silver', label="others")
    for n in range(nStreams):
        ax_slba.plot(datas[list(opcodes == "write") & (streams == n)][key], ".", label="stream=%d " % (n))
        ax_slba.set_ylabel(key)

    ax_latency.clear()
    key = "latency"
    # ax_latency.plot(datas[list(opcodes != 'write')][key], '.', color='silver', label="others")
    for n in range(nStreams):
        ax_latency.plot(datas[list(opcodes == "write") & (streams == n)][key], ".", label="stream=%d " % (n))
        ax_latency.set_ylabel(key)

    plt.xlabel("time")
    plt.legend()
    plt.draw()
    plt.pause(1e-17)


Display_Format = "{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}"
NVMe_dtype = {"timestamp": "float64", "taskid": "category", "nvme": "category", "opcode": "category", "stream": "uint8", "slba": "uint32", "len": "uint16", "latency": "float16"}
NVMe_Columns = ["timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"]


def ViewResult(filename):

    skiprows = 0
    nrows = 100000

    start = time.time()
    # trace_datas = pd.DataFrame()
    # trace_datas = pd.read_csv(filename, header=0, dtype=dtype)
    chunks = pd.read_csv(filename, index_col=0, header=0, dtype=NVMe_dtype, chunksize=1000000)
    # , skiprows= skiprows, nrows=nrows)
    print("elaps {} seconds".format(time.time() - start))

    fig = plt.figure(figsize=(15, 9))
    ax_slba = plt.subplot(211)
    ax_latency = plt.subplot(212)
    fig.tight_layout()

    for chunk in chunks:
        # print(chunk.head())
        graph(chunk, ax_slba, ax_latency)
        trace_datas = pd.concat([chunk])

    print(trace_datas)
    Statistics(trace_datas)

    plt.show()
    return trace_datas


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--display", action="store_true", help="display the reports")
    argparser.add_argument("-o", "--outfile", help="output file")
    argparser.add_argument("-f", "--filename", help="trace data file (csv)")  # nargs='+',
    argparser.add_argument("-v", "--verbose", nargs="?", default="s", help="verbose display")
    args = argparser.parse_args()

    outfilename = "nvme" + time.strftime("-%m%d-%H%M") + ".csv"

    if args.outfile:
        outfilename = args.outfile

    if args.filename:
        ViewResult(args.filename)
    else:
        # app = QtGui.QApplication(sys.argv)
        # thisapp = App()
        # thisapp.show()

        # sys.exit(app.exec_())

        nvmesnoop = CaptureNvme(filename=outfilename, verbose=args.verbose)
        nvmesnoop.start()

        try:
            while 1:
                # datas = np.array(nvmesnoop.getdata())
                # if len(datas):
                #    print(datas[-10:,5])
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

        nvmesnoop.shutdown()
        nvmesnoop.join()
        # print(nvmesnoop.getdata())
        nvmesnoop.summary()

        if args.display:
            ViewResult([outfilename])


if __name__ == "__main__":
    main()
