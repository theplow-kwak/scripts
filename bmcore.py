#!/usr/bin/python3

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import os, re
import argparse
import subprocess
import multiprocessing
import threading
import time
import getpass

class SudoProcess:
    sudo_passwd = None

    def __init__(self, shell=False, passwd=None):
        if shell:
            self.sudo_cmd = 'sudo -S sh -c'.split()
        else:
            self.sudo_cmd = 'sudo -S'.split()
        if passwd:
            SudoProcess.sudo_passwd = passwd
        if SudoProcess.sudo_passwd is None:
            SudoProcess.sudo_passwd = getpass.getpass('password:')

    def Popen(self, commands, wait=True):
        # print(self.sudo_cmd+commands)
        echo_passwd = subprocess.Popen(['echo', self.sudo_passwd], stdout=subprocess.PIPE)
        try:
            cmd = subprocess.Popen(self.sudo_cmd+commands, stdin=echo_passwd.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if wait:
                cmd.communicate()
            else:
                return cmd
        except:
            print('process open error! {}'.format(commands))


class RingBuffer:
    """ class that implements a not-yet-full buffer """
    def __init__(self,size_max):
        self.max = size_max
        self.len = 0
        self.data = []

    class __Full:
        """ class that implements a full buffer """
        def append(self, x):
            """ Append an element overwriting the oldest one. """
            self.data[self.cur] = x
            self.cur = (self.cur+1) % self.max
        def get(self):
            """ return list of elements in correct order """
            return self.data[self.cur:]+self.data[:self.cur]

    def append(self,x):
        """append an element at the end of the buffer"""
        self.data.append(x)
        self.len += 1
        if len(self.data) == self.max:
            self.cur = 0
            # Permanently change self's class from non-full to full
            self.__class__ = self.__Full

    def get(self):
        """ Return a list of elements from the oldest to the newest. """
        self.lock = self.len
        return self.data[:self.len]


from abc import ABCMeta, abstractmethod

class CaptureThread(threading.Thread):
    __metaclass__ = ABCMeta

    name = 'core'
    interval = 1
    logformat = '{0:^20} {1:>12}'
    header = ['timestamp', 'count']

    def __init__(self, filename=None, verbose='s'):
        super(CaptureThread, self).__init__()
        self.exit = threading.Event()
        self.verbose = verbose
        self.tag = 0
        # 't' - test mode, display on consol with 1 sec interval
        # 'c' - display on consol
        # 'f' - save data to file
        self.filename = filename
        if 't' in self.verbose:
            self.verbose += 'c'
            self.interval = 1
        if 'a' in self.verbose:
            self.verbose += 'c'
            self.interval = 0

    def fileopen(self):
        import csv

        if 'f' in self.verbose:
            if self.filename is None:
                self.filename = self.name + '.csv'

            self.__fout = open(self.filename, 'w')
            self.outfile = csv.writer(self.__fout)

            __uid = os.environ.get('SUDO_UID')
            __gid = os.environ.get('SUDO_GID')
            if __uid is not None:
                os.chown(self.filename, int(__uid), int(__gid))

    def logging(self, data):
        if ('c' in self.verbose) and ((time.time() - self.tag) > self.interval):
            print(self.logformat.format(*data))
            self.tag = time.time()
        if 'f' in self.verbose:
            try:
                self.outfile.writerow(data)
            except:
                pass

    def run(self):
        self.fileopen()
        self.logging(self.header)

        while not self.exit.is_set():
            self.work()

        try:
            self.__fout.close()
        except:
            pass

    def shutdown(self):
        self.exit.set()

    @abstractmethod
    def work(self):
        pass

    @abstractmethod
    def summary(self):
        pass


