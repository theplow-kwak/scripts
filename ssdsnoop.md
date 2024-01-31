# ssdsnoop

eBPF/bcc를 사용하여 SATA/ NVMe SSD에 대한 block I/O request 정보를 수집한다. 

수집되는 정보는 다음과 같다.

1.  ts: IO start timestamp.  kernel time(ns)을 second 단위로 표시.
2. taskid: IO를 실행한 Task의 name.
3. major: IO 가 실행되는 disk의 major number.
4.  minor: IO 가 실행되는 disk의 minor number.
5.  disk: IO 가 실행되는 disk name. sata의 경우 'sda', 'sdb' ... 등, nvme의 경우 'nvme0n1', 'nvme1n1'과 같다.
6.  opcode: block layer의 IO command이다. 
7.  cmnd: opcode보다 상세한 row level SCSI command 또는 nvme command .
8.  slba: start LBA (sector address)
9.  len: IO sector counts (1 sector = 512Bytes)
10.  latency: IO start후 complete까지의 microsecond 단위의 latency time 



## How to use

```
usage: ssdsnoop [-h] [-o OUTFILE] [-i INTERVAL] [-v VERBOSE]
                [-f DISKFILTER [DISKFILTER ...]] [-w WORKLOADFILE]
                [-p PAGECOUNT]

'ssdsnoop' collects the workload of the block device.

optional arguments:
  -h, --help            show this help message and exit
  -o OUTFILE, --outfile OUTFILE
                        set the output file name
  -i INTERVAL, --interval INTERVAL
                        set the verbose interval time(seconds)
  -v VERBOSE, --verbose VERBOSE
                        set the verbose display option
                        t - test mode, Display only without saving as a file.
                        a - Display all events.
                        f - save data to outfile. (default)
  -f DISKFILTER [DISKFILTER ...], --diskfilter DISKFILTER [DISKFILTER ...]
                        set the disk filter
  -w WORKLOADFILE, --workloadfile WORKLOADFILE
                        make statistics from workload file                        
```



## example: csv output file

```
ts,taskid,major,minor,disk,opcode,cmnd,slba,len,latency
0.0,kworker/5:1H,8,0,sda,write,42,593709288,8,1720.301
1.5551e-05,kworker/5:1H,8,0,sda,write,42,593709344,8,1782.708
2.0159e-05,kworker/5:1H,8,0,sda,write,42,593709384,8,1795.091
2.4012e-05,kworker/5:1H,8,0,sda,write,42,593709568,8,1801.192
2.8267e-05,kworker/5:1H,8,0,sda,write,42,593709584,8,1821.718
3.2212e-05,kworker/5:1H,8,0,sda,write,42,593709944,24,1829.445
    :
```



## Install BCC binary packages

Ubuntu에서 제공하는 패키지와 iovisor에서 제공하는 패키지의 이름이 다르며 서로 호완되지 않는다: iovisor
packages use `bcc` in the name (e.g. `bcc-tools`), Ubuntu packages use `bpfcc` (e.g.
`bpfcc-tools`). 아래 두가지 방법 중 하나를 선택해야 하며 다른 package는 제거해야 한다.

### Ubuntu

- **Install Ubuntu Packages** (recommend)

```bash
sudo apt-get install bpfcc-tools linux-headers-$(uname -r)
```



- **Upstream Stable and Signed Packages** 

```bash
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 4052245BD4284CDD
echo "deb https://repo.iovisor.org/apt/$(lsb_release -cs) $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/iovisor.list
sudo apt-get update
sudo apt-get install bcc-tools libbcc-examples linux-headers-$(uname -r)
```



### RHEL

RHEL7.6 이상에서 지원되며, package 이름이 Ubuntu와 다르게 'bcc-tools'로 되어있다.

```bash
sudo yum install bcc-tools linux-headers-$(uname -r)
```



------



아래는 package에서 제공하는 bcc-tools를 사용하지 않고 source code를 다운 받아 직접 빌드 및 설치하는 방법이다. package를 사용시에는 필요 없음 

**Install build dependencies** : BCC를 사용하기 위해 필요한 libtary 와 tool들을 미리 설치한다.

```bash
sudo apt install cmake clang libedit-dev llvm libclang-dev libfl-dev libelf-dev
sudo apt install luajit luajit-5.1-dev
sudo apt install netperf iperf bison
sudo apt install python python3 python-pip python3-pip python-tk python3-tk
```



## Install and compile BCC source code

```bash
git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr
make -j `getconf _NPROCESSORS_ONLN`
sudo make install
```



## install python modules

```
pip install pandas -U
pip install matplotlib -U
```





------



# Driver source code 분석

## SCSI init 

scsi_alloc_sdev()

```c
	if (shost_use_blk_mq(shost))
		sdev->request_queue = scsi_mq_alloc_queue(sdev);
	else
		sdev->request_queue = scsi_old_alloc_queue(sdev);
```

```c
struct request_queue *scsi_old_alloc_queue(struct scsi_device *sdev)
{
	q->request_fn = scsi_request_fn;
	q->init_rq_fn = scsi_old_init_rq;
	q->exit_rq_fn = scsi_old_exit_rq;
	q->initialize_rq_fn = scsi_initialize_rq;

	blk_queue_prep_rq(q, scsi_prep_fn);
	blk_queue_unprep_rq(q, scsi_unprep_fn);
	blk_queue_softirq_done(q, scsi_softirq_done);
	blk_queue_rq_timed_out(q, scsi_times_out);
	blk_queue_lld_busy(q, scsi_lld_busy);
}
```

```c
static const struct blk_mq_ops scsi_mq_ops = {
	.get_budget	= scsi_mq_get_budget,
	.put_budget	= scsi_mq_put_budget,
	.queue_rq	= scsi_queue_rq,
	.complete	= scsi_softirq_done,
	.timeout	= scsi_timeout,
	.show_rq	= scsi_show_rq,
	.init_request	= scsi_mq_init_request,
	.exit_request	= scsi_mq_exit_request,
	.initialize_rq_fn = scsi_initialize_rq,
	.map_queues	= scsi_map_queues,
};
```



## NVMe init

```c
static const struct blk_mq_ops nvme_mq_admin_ops = {
	.queue_rq	= nvme_queue_rq,
	.complete	= nvme_pci_complete_rq,
	.init_hctx	= nvme_admin_init_hctx,
	.exit_hctx      = nvme_admin_exit_hctx,
	.init_request	= nvme_init_request,
	.timeout	= nvme_timeout,
};

static const struct blk_mq_ops nvme_mq_ops = {
	.queue_rq	= nvme_queue_rq,
	.complete	= nvme_pci_complete_rq,
	.init_hctx	= nvme_init_hctx,
	.init_request	= nvme_init_request,
	.map_queues	= nvme_pci_map_queues,
	.timeout	= nvme_timeout,
	.poll		= nvme_poll,
};
```



## request flow

### scsi old style (single queue)

q->request_fn = scsi_request_fn;

```
scsi_request_fn ->
  blk_peek_request
  blk_start_request
  scsi_dispatch_cmd ->
    host->hostt->queuecommand
```

### scsi mq

.queue_rq	= scsi_queue_rq

```
scsi_queue_rq ->
  blk_mq_start_request
  scsi_dispatch_cmd ->
    host->hostt->queuecommand
```

### NVMe

.queue_rq	= nvme_queue_rq

```
nvme_queue_rq -> 
  nvme_setup_cmd
  blk_mq_start_request
  nvme_submit_cmd
```



## request completion

* NVMe: 

  ```
  nvme_pci_complete_rq -> 
    nvme_complete_rq -> 
      blk_mq_end_request -> 
        blk_update_request
        __blk_mq_end_request -> 
          blk_account_io_done
  ```

* scsi_softirq_done

  ```
  scsi_softirq_done -> 
    scsi_finish_command -> 
      scsi_io_completion -> 
        scsi_end_request -> 
          blk_update_request
  ```

* scsi_dispatch_cmd_done

  ```
  scsi single queue: 
  scsi_done -> 
    blk_complete_request -> 
      __blk_complete_request -> 
  ```

  ```
  scsi multi queue: 
  scsi_mq_done -> 
    blk_mq_complete_request -> 
      __blk_mq_complete_request -> 
  ```


* blk_update_request

  ```
  scsi single queue: 
  blk_update_bidi_request -> 
    blk_update_request
  ```

  ```
  scsi multi queue: 
  blk_mq_end_request -> 
    blk_update_request
  ```