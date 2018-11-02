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
        self.__opcode_exp = re.compile(r'cmd=\((?P<opcode>\w+)')

    def parse(self, line):
        try:
            __tresult = self.__trace_exp.search(line).groupdict()
            __opcode = self.__opcode_exp.search(line)
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

    def lookup(self, key):
        try:
            return self.stack[key]
        except:
            pass
        #for rkey, value in self.stack.items():
        #    if key == rkey:
        #        return value

    def start(self, key, value):
        self.stack[key] = value

    def delete(self, key):
        del self.stack[key]


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
    'nvme_admin_delete_sq':     0x100,
    'nvme_admin_create_sq':     0x101,
    'nvme_admin_get_log_page':  0x102,
    'nvme_admin_delete_cq':     0x104,
    'nvme_admin_create_cq':     0x105,
    'nvme_admin_identify':      0x106,
    'nvme_admin_abort_cmd':     0x108,
    'nvme_admin_set_features':  0x109,
    'nvme_admin_get_features':  0x10a,
    'nvme_admin_async_event':   0x10c,
    'nvme_admin_ns_mgmt':       0x10d,
    'nvme_admin_activate_fw':   0x110,
    'nvme_admin_download_fw':   0x111,
    'nvme_admin_ns_attach':     0x115,
    'nvme_admin_keep_alive':    0x118,
    'nvme_admin_directive_send': 0x119,
    'nvme_admin_directive_recv': 0x11a,
    'nvme_admin_dbbuf':         0x17C,
    'nvme_admin_format_nvm':    0x180,
    'nvme_admin_security_send': 0x181,
    'nvme_admin_security_recv': 0x182,
    'nvme_admin_sanitize_nvm':  0x184,
}

nvme_cmd_opcode = {
    'nvme_cmd_flush':           0x00,
    'nvme_cmd_write':           0x01,
    'nvme_cmd_read':            0x02,
    'nvme_cmd_write_uncor':     0x04,
    'nvme_cmd_compare':         0x05,
    'nvme_cmd_write_zeroes':    0x08,
    'nvme_cmd_dsm':             0x09,
    'nvme_cmd_resv_register':   0x0d,
    'nvme_cmd_resv_report':     0x0e,
    'nvme_cmd_resv_acquire':    0x11,
    'nvme_cmd_resv_release':    0x15,
}

nvme_opcode = {**nvme_cmd_opcode, **nvme_admin_opcode}

class TraceLog:

    def read_logs(infile, outfile):
        traceLogs = {}
        parser = TraceParser()
        request = RequestComplition()
        index = 0
        tag = time.time()

        print('{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}'.format(
            'index', 'timestamp', 'taskid', 'nvme', 'opcode', 'stream', 'slba', 'len', 'latency'))

        try:
            for line in infile:
                tresult = parser.parse(line.strip())

                if tresult:

                    if tresult['event'] == "nvme_setup_admin_cmd":
                        result = [to_num(tresult['timestamp']), tresult['taskid'], '', tresult['opcode'].replace('nvme_admin_',''), 0, 0, 0, 0]
                        request.start(tresult['cmdid'], result)
                        #traceLogs[last] = result
                        #last += 1

                    if tresult['event'] == "nvme_setup_nvm_cmd":
                        try:
                            tresult['stream'] = to_num(tresult['dsmgmt']) >> 16
                        except:
                            tresult['stream'] = 0

                        result = [to_num(tresult['timestamp']), tresult['taskid'], tresult.get('nvme','nvme0n1'), tresult['opcode'].replace('nvme_cmd_',''), tresult['stream'],
                                  to_num(tresult.get('slba',0)), to_num(tresult.get('len',0)), 0]
                        request.start(tresult['cmdid'], result)

                        #traceLogs[last] = result
                        #last += 1

                    if tresult['event'] == "nvme_complete_rq":
                        result = request.lookup(tresult['cmdid'])
                        if result:
                            request.delete(tresult['cmdid'])
                            result[7] = round(to_num(tresult['timestamp']) - result[0], 6)
                            index += 1
                            outfile.writerow(result)
                            if (time.time() - tag) > 1:
                                print('{:>8} {:>16} {:^16} {:^10} {:^16} {:^6} {:>14} {:>7} {:>16}'.format(index, *result))
                                tag = time.time()


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
    argparser.add_argument('-o', '--opcode', nargs='+', help='set opcode filter')

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
            infile = open(args.rawfile, 'r', encoding='UTF8')
            o_filename = args.rawfile + ".csv"

        import csv

        __fout = open(o_filename, 'w')
        outfile = csv.writer(__fout)

        start = time.time()
        trace_datas = pd.DataFrame.from_dict(TraceLog.read_logs(infile, outfile), orient='index', columns=['timestamp', 'taskid', 'nvme', 'opcode', 'stream', 'slba', 'len', 'latency'])
#        TraceLog.read_logs(infile)
        end = time.time()
        print("labs time: ", end - start, "\n")

        #trace_datas.to_csv(outfile, index=False)

    print(trace_datas.memory_usage())

    if args.visualize:
        print("\n\n Operation counts and data size: \n", trace_datas.pivot_table(values='len', index='stream', columns=['opcode'], aggfunc=['count', 'sum'], fill_value=0))
        print("\n\n LBA describes per each stream: \n", trace_datas.groupby('stream')['slba'].describe())
        print("\n\n length describes per each stream: \n", trace_datas.groupby('stream')['len'].describe())
        print("\n\n latency describes per each stream: \n", trace_datas.groupby('stream')['latency'].describe())

        nStreams = trace_datas['stream'].max() + 1
        fig = plt.figure(figsize=(15, 9))

        filtered = trace_datas[(trace_datas.nvme == 'nvme0n1')]
        if args.opcode :
            filtered = filtered[filtered.opcode.isin(args.opcode)]

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

        plt.legend()
        fig.tight_layout()
        plt.show()

#    main("nvme.log")
#    app = wx.App()
#    frm = NVMeParser(None)
#    frm.Show()
#    app.MainLoop()
