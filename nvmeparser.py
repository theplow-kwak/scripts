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
        taskid = '\s*(?P<taskid>.+)-(?:\d+)'
        cpuid = '\s+(?:\[\d+\])(?:\s.{4})'
        timestamp = '\s+(?P<timestamp>\d+.\d+):'
        event = '\s+(?P<event>\w+):'
        self.__trace_exp = re.compile(taskid + cpuid + timestamp + event)
        self.__keyval_exp = re.compile(r'\s?(?P<key>\w+)=(?P<val>\w+),?')
        self.__cmd_exp = re.compile(r'cmd=\(nvme_cmd_(?P<opcode>\w+)')
        self.__admin_exp = re.compile(r'cmd=\(nvme_admin_(?P<opcode>\w+)')

    def parse(self, line):
        try:
            __tresult = self.__trace_exp.search(line).groupdict()
            __opcode = self.__cmd_exp.search(line)
            if __opcode:
                __tresult.update(__opcode.groupdict())
            __params = self.__keyval_exp.findall(line)
            if __params:
                __tresult.update(dict(__params))
            return __tresult
        except Exception as e:
            print(e)
            print(line, "\n")
            pass


class RequestComplition:
    stack = {}

    def lookup(self, values):
        for key, value in self.stack.items():
            if value == values:
                return key
        return -1

    def start(self, key, values):
        self.stack[key] = values

    def completion(self, values):
        key = self.lookup(values)
        if key != -1:
            del self.stack[key]
        return key


def to_num(str_num):
    try:
        return float(str_num) if '.' in str_num else int(str_num, 0)
    except:
        return str_num


nvme_event = {
    'nvme_setup_admin_cmd': 1,
    'nvme_setup_nvm_cmd': 2,
    'nvme_complete_rq': 3
}

nvme_admin_opcode = {
    'nvme_admin_delete_sq': 0x100,
    'nvme_admin_create_sq': 0x101,
    'nvme_admin_get_log_page': 0x102,
    'nvme_admin_delete_cq': 0x104,
    'nvme_admin_create_cq': 0x105,
    'nvme_admin_identify': 0x106,
    'nvme_admin_abort_cmd': 0x108,
    'nvme_admin_set_features': 0x109,
    'nvme_admin_get_features': 0x10a,
    'nvme_admin_async_event': 0x10c,
    'nvme_admin_ns_mgmt': 0x10d,
    'nvme_admin_activate_fw': 0x110,
    'nvme_admin_download_fw': 0x111,
    'nvme_admin_ns_attach': 0x115,
    'nvme_admin_keep_alive': 0x118,
    'nvme_admin_directive_send': 0x119,
    'nvme_admin_directive_recv': 0x11a,
    'nvme_admin_dbbuf': 0x17C,
    'nvme_admin_format_nvm': 0x180,
    'nvme_admin_security_send': 0x181,
    'nvme_admin_security_recv': 0x182,
    'nvme_admin_sanitize_nvm': 0x184,
}

nvme_cmd_opcode = {
    'nvme_cmd_flush': 'f',
    'nvme_cmd_write': 'w',
    'nvme_cmd_read': 'r',
    'nvme_cmd_write_uncor': 'u',
    'nvme_cmd_compare	': 'c',
    'nvme_cmd_write_zeroes': 'z',
    'nvme_cmd_dsm': 'd',
    'nvme_cmd_resv_register': 0x0d,
    'nvme_cmd_resv_report': 0x0e,
    'nvme_cmd_resv_acquire': 0x11,
    'nvme_cmd_resv_release': 0x15,
}

nvme_opcode = {**nvme_cmd_opcode, **nvme_admin_opcode}

class TraceLog:

    def read_logs(file):
        traceLogs = {}
        parser = TraceParser()
        request = RequestComplition()
        last = 0
        tag = time.time()

        try:
            for line in file:
                tresult = parser.parse(line.strip())

                if tresult:
                    #tresult['timestamp'] = int(tresult['timestamp'].replace('.', ''))

                    if tresult['event'] in ["nvme_setup_nvm_cmd"]:
                        request.start(last, tresult['cmdid'])

                        for k, v in tresult.items():
                            tresult[k] = to_num(v)
                        try:
                            tresult['stream'] = tresult['dsmgmt'] >> 16
                        except:
                            tresult['stream'] = 0

                        if (time.time() - tag) > 1:
                            print("%5d: %s \tcmdid: %s \ttimestamp: %s \ttaskid: %12s \tstream: %d" % (
                                last, tresult['opcode'], tresult['cmdid'], tresult['timestamp'], tresult['taskid'], tresult['stream']))
                            tag = time.time()

                        tresult['event'] = nvme_event[tresult['event']]
                        #if tresult['opcode'] in nvme_opcode:
                        #    tresult['opcode'] = nvme_opcode[tresult['opcode']]

                        traceLogs[last] = {}
                        traceLogs[last].update(tresult)
                        last += 1

                    elif tresult['event'] == "nvme_complete_rq":
                        index = request.completion(tresult['cmdid'])
                        if index != -1:
                            traceLogs[index]['latency'] = round(to_num(tresult['timestamp']) - traceLogs[index]['timestamp'], 6)

        except KeyboardInterrupt:
            sys.stdout.flush()
            pass

        return traceLogs

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
    argparser.add_argument('-r', '--rawfile', help='raw trace input file')
    argparser.add_argument('-f', '--filename', nargs='+', help='trace data file (csv)')
    argparser.add_argument('-v', '--visualize', action='store_true', help='display the reports')
    argparser.add_argument('-p', '--outpath', help='output path')

    args = argparser.parse_args()

    if args.filename:
        trace_datas = pd.DataFrame([])
        for _file in args.filename:
            trace_datas = trace_datas.append(pd.read_csv(_file), ignore_index=True, sort=False)
    else:
        infile = sys.stdin
        if args.outpath:
            outfile = args.outpath
        else:
            outfile = "nvme" + time.strftime("-%m%d-%H%M") + ".csv"
        if args.rawfile:
            infile = open(args.rawfile, 'r', encoding='UTF8')
            outfile = args.rawfile + ".csv"

        start = time.time()
        trace_datas = pd.DataFrame.from_dict(TraceLog.read_logs(infile), orient='index')
        end = time.time()
        print("labs time: ", end - start, "\n")

        trace_datas.to_csv(outfile, index=False)

        print(trace_datas.memory_usage())

    if args.visualize:
        print("\n\n Operation counts and data size: \n", trace_datas.pivot_table(values='len', index='stream', columns=['opcode'], aggfunc=['count', 'sum'], fill_value=0))
        print("\n\n LBA describes per each stream: \n", trace_datas.groupby('stream')['slba'].describe())
        print("\n\n length describes per each stream: \n", trace_datas.groupby('stream')['len'].describe())
        print("\n\n latency describes per each stream: \n", trace_datas.groupby('stream')['latency'].describe())

        nStreams = trace_datas['stream'].max() + 1
        fig = plt.figure(figsize=(15, 9))

        filtered = trace_datas[trace_datas.name == 'nvme0n1']
        key = 'slba'
        plt.subplot(211)
        for n in range(nStreams):
            plt.plot(filtered[filtered.stream == n][key], '.', label="stream=%d " % (n))
        plt.ylabel(key)

        key = 'latency'
        plt.subplot(212)
        for n in range(nStreams):
            plt.plot(filtered[filtered.stream == n][key], '.', label="stream=%d " % (n))
        plt.ylabel(key)

        filtered = trace_datas[trace_datas.name != 'nvme0n1']
        plt.subplot(211)
        plt.plot(filtered['slba'], '.', label="!nvme0n1", color='b')
        plt.subplot(212)
        plt.plot(filtered['latency'], '.', label="!nvme0n1", color='b')

        plt.legend()
        fig.tight_layout()
        plt.show()

"""
    key = 'len'
    plt.subplot(312)
    for n in range(nStreams):
        plt.plot(trace_datas[trace_datas.stream == n][key], '.', label="stream=%d " % (n))
    plt.ylabel(key)
"""
#    main("nvme.log")
#    app = wx.App()
#    frm = NVMeParser(None)
#    frm.Show()
#    app.MainLoop()
