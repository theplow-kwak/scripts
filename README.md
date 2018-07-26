
# nvmesnoop.py: Collects information of NVMe request using eBPF/bcc.

## install bcc package

### Install build dependencies
sudo apt install cmake clang libedit-dev llvm libclang-dev luajit libfl-dev
sudo apt install luajit luajit-5.1-dev
sudo apt install netperf iperf 

### Install and compile BCC
git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_CMD=python3
make
sudo make install


## How to use
usage: nvmesnoop.py [-h] [-v] [-o OUTFILE] [-f FILENAME [FILENAME ...]] [-d]

optional arguments:
  -h, --help            show this help message and exit
  -v, --visualize       display the reports
  -o OUTFILE, --outfile OUTFILE
                        output file
  -f FILENAME [FILENAME ...], --filename FILENAME [FILENAME ...]
                        trace data file (csv)
  -d, --display         verbose display

## csv output file
timestamp,taskid,nvme,opcode,stream,slba,len,latency
143150.017680594,krusader,nvme0n1,read,0,60295232,255,0.000488964
     :
