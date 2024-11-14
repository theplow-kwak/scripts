#!/usr/bin/python3

import sys
import os
import argparse
import re
import time
import pandas as pd
import matplotlib.pyplot as plt


# from nvmeparserui import *


class TraceParser:
    def __init__(self):
        # ------------------------------------------------------------------------
        # Define Grammars
        # ------------------------------------------------------------------------
        self.params = {}

    def parse(self, line):
        try:
            self.__taskid = line[:22].strip()
            self.__cpuid = line[24:27]
            self.__tresult = re.split("[ ,)] *", line[35:])
            self.event = self.__tresult[1]
            self.__timestamp = float(self.__tresult[0].rstrip(":"))
            self.result = [self.__timestamp]
            for x in self.__tresult[2:13]:
                try:
                    key, val = x.split("=")
                    self.params[key] = val
                except:
                    continue

            self.req_key = self.__cpuid + self.params["cmdid"]
            if self.event == "nvme_setup_admin_cmd:":
                self.result = [self.__timestamp, self.__taskid, "", self.params["cmd"].replace("(nvme_admin_", ""), 0, 0, 0, 0]
            if self.event == "nvme_setup_nvm_cmd:":
                self.result = [
                    self.__timestamp,
                    self.__taskid,
                    self.params.get("nvme", ""),
                    self.params["cmd"].replace("(nvme_cmd_", ""),
                    int(self.params.get("dsmgmt", 0)) >> 16,
                    self.params.get("slba", 0),
                    self.params.get("len", 0),
                    0,
                ]

            return self.event, self.req_key, self.result

        except Exception as e:
            print("\n", e)
            print(line, "\n")
            return None, None, None


class RequestComplition:
    def __init__(self):
        self.stack = {}

    def lookup(self, key):
        try:
            return self.stack[key]
        except:
            pass

    def start(self, key, value):
        self.stack[key] = value

    def delete(self, key):
        del self.stack[key]


def to_num(str_num):
    try:
        return float(str_num) if "." in str_num else int(str_num, 0)
    except:
        return str_num


nvme_event = {"nvme_setup_admin_cmd": 1, "nvme_setup_nvm_cmd": 2, "nvme_complete_rq": 3}

nvme_admin_opcode = {
    "nvme_admin_delete_sq": 0x100,
    "nvme_admin_create_sq": 0x101,
    "nvme_admin_get_log_page": 0x102,
    "nvme_admin_delete_cq": 0x104,
    "nvme_admin_create_cq": 0x105,
    "nvme_admin_identify": 0x106,
    "nvme_admin_abort_cmd": 0x108,
    "nvme_admin_set_features": 0x109,
    "nvme_admin_get_features": 0x10A,
    "nvme_admin_async_event": 0x10C,
    "nvme_admin_ns_mgmt": 0x10D,
    "nvme_admin_activate_fw": 0x110,
    "nvme_admin_download_fw": 0x111,
    "nvme_admin_ns_attach": 0x115,
    "nvme_admin_keep_alive": 0x118,
    "nvme_admin_directive_send": 0x119,
    "nvme_admin_directive_recv": 0x11A,
    "nvme_admin_dbbuf": 0x17C,
    "nvme_admin_format_nvm": 0x180,
    "nvme_admin_security_send": 0x181,
    "nvme_admin_security_recv": 0x182,
    "nvme_admin_sanitize_nvm": 0x184,
}

nvme_cmd_opcode = {
    "nvme_cmd_flush": 0x00,
    "nvme_cmd_write": 0x01,
    "nvme_cmd_read": 0x02,
    "nvme_cmd_write_uncor": 0x04,
    "nvme_cmd_compare": 0x05,
    "nvme_cmd_write_zeroes": 0x08,
    "nvme_cmd_dsm": 0x09,
    "nvme_cmd_resv_register": 0x0D,
    "nvme_cmd_resv_report": 0x0E,
    "nvme_cmd_resv_acquire": 0x11,
    "nvme_cmd_resv_release": 0x15,
}

nvme_opcode = {**nvme_cmd_opcode, **nvme_admin_opcode}


class TraceLog:
    logformat = "{:>8} {:<20} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}"
    header = ["index", "timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"]

    def __init__(self):
        self.traceLogs = {}
        self.parser = TraceParser()
        self.request = RequestComplition()
        self.index = 0

    def read_logs(self, infile, outfile):
        self.tag = time.time()

        print("{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}".format("index", "timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"))
        outfile.writerow(["timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"])

        for line in infile:
            try:
                event, req_key, req_val = self.parser.parse(line.rstrip("\n)"))

                if event == "nvme_complete_rq:":
                    result = self.request.lookup(req_key)
                    if result:
                        self.request.delete(req_key)
                        result[7] = round(req_val[0] - result[0], 6)
                        self.index += 1
                        outfile.writerow(result)
                        if (time.time() - self.tag) > 1:
                            print("{:>8} {:>16} {:^22} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}".format(self.index, *result))
                            self.tag = time.time()
                else:
                    self.request.start(req_key, req_val)

            except ValueError:
                continue

            except KeyboardInterrupt:
                sys.stdout.flush()
                pass

        return self.traceLogs


"""
def plot(key, ):
    key = 'slba'
    plt.subplot(211)
    for n in range(nStreams):
        plt.plot(trace_datas[trace_datas.stream == n][key], '.', label="stream=%d " % (n,))
    plt.ylabel(key)
"""

if __name__ == "__main__":

    argparser = argparse.ArgumentParser()
    argparser.add_argument("-r", "--rawfile", help="raw trace input file")
    argparser.add_argument("-f", "--filename", nargs="+", help="trace data file (csv)")
    argparser.add_argument("-v", "--visualize", action="store_true", help="display the reports")
    argparser.add_argument("-p", "--outpath", help="output path")
    argparser.add_argument("-o", "--opcode", nargs="+", help="set opcode filter")

    args = argparser.parse_args()

    if args.filename:
        trace_datas = pd.DataFrame([])
        for _file in args.filename:
            trace_datas = trace_datas.append(pd.read_csv(_file), ignore_index=True, sort=False)
    else:
        infile = sys.stdin
        if args.outpath:
            o_filename = args.outpath
        else:
            o_filename = "nvme" + time.strftime("-%m%d-%H%M") + ".csv"
        if args.rawfile:
            infile = open(args.rawfile, "r", encoding="UTF8")
            o_filename = args.rawfile + ".csv"

        import csv

        __fout = open(o_filename, "w")
        outfile = csv.writer(__fout)
        tracer = TraceLog()

        start = time.time()
        trace_datas = pd.DataFrame.from_dict(
            tracer.read_logs(infile, outfile), orient="index", columns=["timestamp", "taskid", "nvme", "opcode", "stream", "slba", "len", "latency"]
        )
        #        TraceLog.read_logs(infile)
        end = time.time()
        print("labs time: ", end - start, "\n")

        # trace_datas.to_csv(outfile, index=False)

    print(trace_datas.memory_usage())

    if args.visualize:
        print("\n\n Operation counts and data size: \n", trace_datas.pivot_table(values="len", index="stream", columns=["opcode"], aggfunc=["count", "sum"], fill_value=0))
        print("\n\n LBA describes per each stream: \n", trace_datas.groupby("stream")["slba"].describe())
        print("\n\n length describes per each stream: \n", trace_datas.groupby("stream")["len"].describe())
        print("\n\n latency describes per each stream: \n", trace_datas.groupby("stream")["latency"].describe())

        nStreams = trace_datas["stream"].max() + 1
        fig = plt.figure(figsize=(15, 9))

        filtered = trace_datas[(trace_datas.nvme == "nvme0n1")]
        if args.opcode:
            filtered = filtered[filtered.opcode.isin(args.opcode)]

        key = "slba"
        plt.subplot(211)
        for n in range(nStreams):
            plt.plot(filtered[filtered.stream == n][key], ".", label="stream=%d " % (n))
        plt.ylabel(key)

        key = "latency"
        plt.subplot(212)
        for n in range(nStreams):
            plt.plot(filtered[filtered.stream == n][key], ".", label="stream=%d " % (n))
        plt.ylabel(key)

        plt.legend()
        fig.tight_layout()
        plt.show()

#    main("nvme.log")
#    app = wx.App()
#    frm = NVMeParser(None)
#    frm.Show()
#    app.MainLoop()
