#include <uapi/linux/ptrace.h>
#include <linux/blkdev.h>
#include <linux/blk_types.h>
#include <linux/nvme.h>
#include <scsi/scsi_cmnd.h>

#ifndef SECTOR_SHIFT
#define SECTOR_SHIFT 9
#endif

#define _(P) ({typeof(P) _val = 0; bpf_probe_read(&_val, sizeof(_val), &P); _val;})

struct val_t {
    u64 io_start_time_ns;
    char taskid[TASK_COMM_LEN];
};

struct cmd_data_t {
    u64 io_start_time_ns;
    char taskid[TASK_COMM_LEN];
    char disk_name[DISK_NAME_LEN];
    u8 opcode;
    u8 cmnd;
    u64 slba;
    u32 len;
    u64 latency_ns;
    u16 major;
    u16 minor;
};

struct nvme_request {
    struct nvme_command	*cmd;
    union nvme_result	result;
    u8			retries;
    u8			flags;
    u16			status;
};

typedef struct key_type {
    char disk_name[DISK_NAME_LEN];
    u16 opcode;
    u16 cmnd;
} key_type_t;

BPF_HASH(start, struct request *, struct val_t);
BPF_PERF_OUTPUT(events);
//BPF_HISTOGRAM(latency_hist);
//BPF_HASH(statistics, key_type_t);

static inline u16 get_unaligned_be16(const u8 *p)
{
	return p[0] << 8 | p[1];
}

static inline u32 get_unaligned_be32(const u8 *p)
{
	return p[0] << 24 | p[1] << 16 | p[2] << 8 | p[3];
}

static inline u64 get_unaligned_be64(const u8 *p)
{
	return (u64)get_unaligned_be32(p) << 32 |
	       get_unaligned_be32(p + 4);
}

#define SERVICE_ACTION16(cdb) (cdb[1] & 0x1f)
#define SERVICE_ACTION32(cdb) ((cdb[8] << 8) | cdb[9])


static inline void
scsi_trace_rw6(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = ((cdb[1] & 0x1F) << 16);
	param->slba |= (cdb[2] << 8);
	param->slba |= cdb[3];
	param->len = cdb[4];

	return;
}

static inline void
scsi_trace_rw10(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = (cdb[2] << 24);
	param->slba |= (cdb[3] << 16);
	param->slba |= (cdb[4] << 8);
	param->slba |= cdb[5];
	param->len = (cdb[7] << 8);
	param->len |= cdb[8];

	if (cdb[0] == WRITE_SAME) {
		param->slba = cdb[1] >> 3 & 1;
		param->len = 0;
	}
	return;
}

static inline void
scsi_trace_rw12(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = (cdb[2] << 24);
	param->slba |= (cdb[3] << 16);
	param->slba |= (cdb[4] << 8);
	param->slba |= cdb[5];
	param->len = (cdb[6] << 24);
	param->len |= (cdb[7] << 16);
	param->len |= (cdb[8] << 8);
	param->len |= cdb[9];

	return;
}

static inline void
scsi_trace_rw16(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = ((u64)cdb[2] << 56);
	param->slba |= ((u64)cdb[3] << 48);
	param->slba |= ((u64)cdb[4] << 40);
	param->slba |= ((u64)cdb[5] << 32);
	param->slba |= (cdb[6] << 24);
	param->slba |= (cdb[7] << 16);
	param->slba |= (cdb[8] << 8);
	param->slba |= cdb[9];
	param->len = (cdb[10] << 24);
	param->len |= (cdb[11] << 16);
	param->len |= (cdb[12] << 8);
	param->len |= cdb[13];

	if (cdb[0] == WRITE_SAME_16) {
		param->slba = cdb[1] >> 3 & 1;
		param->len = 0;
	}	

	return;
}

static inline void
scsi_trace_rw32(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = ((u64)cdb[12] << 56);
	param->slba |= ((u64)cdb[13] << 48);
	param->slba |= ((u64)cdb[14] << 40);
	param->slba |= ((u64)cdb[15] << 32);
	param->slba |= (cdb[16] << 24);
	param->slba |= (cdb[17] << 16);
	param->slba |= (cdb[18] << 8);
	param->slba |= cdb[19];
	param->len = (cdb[28] << 24);
	param->len |= (cdb[29] << 16);
	param->len |= (cdb[30] << 8);
	param->len |= cdb[31];

	if (SERVICE_ACTION32(cdb) == WRITE_SAME_32) {
		param->slba = cdb[10] >> 3 & 1;
		param->len = 0;
	}

	return;
}

static inline void
scsi_trace_unmap(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = cdb[7] << 8 | cdb[8];

	return;
}

static inline void
scsi_trace_service_action_in(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = ((u64)cdb[2] << 56);
	param->slba |= ((u64)cdb[3] << 48);
	param->slba |= ((u64)cdb[4] << 40);
	param->slba |= ((u64)cdb[5] << 32);
	param->slba |= (cdb[6] << 24);
	param->slba |= (cdb[7] << 16);
	param->slba |= (cdb[8] << 8);
	param->slba |= cdb[9];
	param->len = (cdb[10] << 24);
	param->len |= (cdb[11] << 16);
	param->len |= (cdb[12] << 8);
	param->len |= cdb[13];

	return;
}

static inline void
scsi_trace_maintenance_in(unsigned char* cdb, struct cmd_data_t *param)
{
	param->len = get_unaligned_be32(&cdb[6]);

	return;
}

static inline void
scsi_trace_maintenance_out(unsigned char* cdb, struct cmd_data_t *param)
{
	param->len = get_unaligned_be32(&cdb[6]);

	return;
}

#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
static inline void
scsi_trace_zbc_in(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = get_unaligned_be64(&cdb[2]);
	param->len = get_unaligned_be32(&cdb[10]);

	return;
}

static inline void
scsi_trace_zbc_out(unsigned char* cdb, struct cmd_data_t *param)
{
	param->slba = get_unaligned_be64(&cdb[2]);

	return;
}
#endif

static inline void
scsi_trace_varlen(unsigned char* cdb, struct cmd_data_t *param)
{
	switch (SERVICE_ACTION32(cdb)) {
	case READ_32:
	case VERIFY_32:
	case WRITE_32:
	case WRITE_SAME_32:
		return scsi_trace_rw32(cdb, param);
	default:
		break;
	}
}

static inline void
scsi_trace_parse_cdb(unsigned char* cdb, struct cmd_data_t *param)
{
	switch (cdb[0]) {
	case READ_6:
	case WRITE_6:
		scsi_trace_rw6(cdb, param);
		break;
	case READ_10:
	case VERIFY:
	case WRITE_10:
	case WRITE_SAME:
		scsi_trace_rw10(cdb, param);
		break;
	case READ_12:
	case VERIFY_12:
	case WRITE_12:
		scsi_trace_rw12(cdb, param);
		break;
	case READ_16:
	case VERIFY_16:
	case WRITE_16:
	case WRITE_SAME_16:
		scsi_trace_rw16(cdb, param);
		break;
	case UNMAP:
		scsi_trace_unmap(cdb, param);
		break;
	case SERVICE_ACTION_IN_16:
		scsi_trace_service_action_in(cdb, param);
		break;
	case VARIABLE_LENGTH_CMD:
		scsi_trace_varlen(cdb, param);
		break;
	case MAINTENANCE_IN:
		scsi_trace_maintenance_in(cdb, param);
		break;
	case MAINTENANCE_OUT:
		scsi_trace_maintenance_out(cdb, param);
		break;
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
	case ZBC_IN:
		scsi_trace_zbc_in(cdb, param);
		break;
	case ZBC_OUT:
		scsi_trace_zbc_out(cdb, param);
		break;
#endif
	default:
		param->slba = 0;
		param->len = 0;
		break;
	}
}


#if LINUX_VERSION_CODE <= KERNEL_VERSION(4,15,0)
static inline int rq_op(u64 flags)
{
    if (flags & REQ_OP_DISCARD)
        return REQ_OP_DISCARD;
    else if (flags & REQ_OP_WRITE_SAME)
        return REQ_OP_WRITE_SAME;
    else if (flags & REQ_OP_WRITE)
        return REQ_OP_WRITE;
    else
        return REQ_OP_READ;
}

#define req_data_dir(flag) (op_is_write(op_from_rq_bits(flag)) ? WRITE : READ)

#else
static inline int rq_op(u64 flags)
{
    return flags & REQ_OP_MASK;
}
#endif

int blk_req_start(struct pt_regs *ctx, struct request *req)
{
    struct val_t *valp;
    struct val_t val = {};

    bpf_get_current_comm(&val.taskid, sizeof(val.taskid));
    val.io_start_time_ns = bpf_ktime_get_ns();
    start.update(&req, &val);
    // bpf_trace_printk("blk_req_start %x %x \n", req, val.cmnd);

    return 0;
}

int blk_req_completion(struct pt_regs *ctx, struct request *req)
{
    struct val_t *valp;
    struct gendisk *rq_disk;
    struct cmd_data_t data = {};

    valp = start.lookup(&req);
    if (valp == 0) {
        // bpf_trace_printk("missed tracing issue %x %d %d \n", req, req->__sector, req->__data_len >> 9);
        return 0;
    }

    bpf_probe_read_str(&data.taskid, sizeof(data.taskid), valp->taskid);
    data.io_start_time_ns = valp->io_start_time_ns;
    data.latency_ns = bpf_ktime_get_ns() - data.io_start_time_ns;
    start.delete(&req);

    data.opcode = rq_op(req->cmd_flags);
    data.len = req->__data_len >> SECTOR_SHIFT;
    if(data.len)
    {
        data.slba = req->__sector;
    }
	
    rq_disk = req->rq_disk;
    bpf_probe_read_str(&data.disk_name, sizeof(data.disk_name), rq_disk->disk_name);
	data.major = rq_disk->major;
	data.minor = rq_disk->first_minor;
	
    if(data.major == 259) {
#if LINUX_VERSION_CODE <= KERNEL_VERSION(4,15,0)
		if (req->cmd_type == REQ_TYPE_DRV_PRIV)
			data.cmnd = ((struct nvme_command *)((struct nvme_request*)(req+1))->cmd)->common.opcode;
		else if (req->cmd_flags & REQ_FLUSH)
			data.cmnd = nvme_cmd_flush;
		else if (req->cmd_flags & REQ_DISCARD)
			data.cmnd = nvme_cmd_dsm;
		else
			data.cmnd = (req_data_dir(_(req->cmd_flags)) ? nvme_cmd_write : nvme_cmd_read);
#else
		switch (rq_op(req->cmd_flags)) {
			case REQ_OP_DRV_IN:
			case REQ_OP_DRV_OUT:
				data.cmnd = ((struct nvme_command *)((struct nvme_request*)(req+1))->cmd)->common.opcode;
				break;
			case REQ_OP_FLUSH:
				data.cmnd = nvme_cmd_flush;
				break;
			case REQ_OP_WRITE_ZEROES:
				/* currently only aliased to deallocate for a few ctrls: */
			case REQ_OP_DISCARD:
				data.cmnd = nvme_cmd_dsm;
				break;
			case REQ_OP_READ:
			case REQ_OP_WRITE:
				data.cmnd = (rq_op(req->cmd_flags) & 1) ? nvme_cmd_write : nvme_cmd_read;
				break;
			default:
				data.cmnd = ((struct nvme_command *)((struct nvme_request*)(req+1))->cmd)->common.opcode;
		}
#endif
    }else {
		unsigned char *cmnd = ((struct scsi_cmnd *)req->special)->cmnd;
		data.cmnd = cmnd[0];
#if LINUX_VERSION_CODE <= KERNEL_VERSION(4,15,0)
		if( data.opcode == REQ_TYPE_DRV_PRIV )
#else
		if( data.opcode == REQ_OP_SCSI_IN || data.opcode == REQ_OP_SCSI_OUT )
#endif
		{
			#define MAX_CDB 32
			unsigned char cdb[MAX_CDB];
			unsigned short cmd_len = ((struct scsi_cmnd *)req->special)->cmd_len;
			int len = cmd_len > MAX_CDB ? MAX_CDB : cmd_len;
			
			bpf_probe_read(&cdb, len, cmnd);	
			scsi_trace_parse_cdb(cdb, &data);
		} 
	}

    events.perf_submit(ctx, &data, sizeof(data));
    // bpf_trace_printk("blk_req_completion %x %x \n", req, data.cmnd);

    return 0;
}
