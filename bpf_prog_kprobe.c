#include <uapi/linux/ptrace.h>
#include <linux/blkdev.h>
#include <linux/blk_types.h>
#include <linux/nvme.h>
#include <scsi/scsi_cmnd.h>
#include <scsi/scsi_request.h>

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
    s64 latency_ns;
    u16 major;
    u16 minor;
    u8 ata_cmd;
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
scsi_trace_ata_pass_thru(unsigned char* cdb, struct cmd_data_t *param)
{
	if (cdb[0] == ATA_16) {
		param->slba = (cdb[12] << 16);
		param->slba |= (cdb[10] << 8);
		param->slba |= cdb[8];
		param->len = cdb[6];		
		param->ata_cmd = cdb[14];
	} else if (cdb[0] == ATA_12) {
		param->slba = (cdb[7] << 16);
		param->slba |= (cdb[6] << 8);
		param->slba |= cdb[5];
		param->len = cdb[4];		
		param->ata_cmd = cdb[9];
	} else {
		param->slba = (cdb[17] << 16);
		param->slba |= (cdb[18] << 8);
		param->slba |= cdb[19];
		param->len = cdb[23];		
		param->ata_cmd = cdb[25];
	}
	return;
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
	case ATA_12:
	case ATA_16:
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
	case ATA_32:
#endif
		scsi_trace_ata_pass_thru(cdb, param);
		break;
	default:
		param->slba = 0;
		param->len = 0;
		break;
	}
}


#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
static inline int rq_op(u64 flags)
{
    return flags & REQ_OP_MASK;
}
#else
static inline int rq_op(u64 flags)
{
    if (flags & REQ_OP_DISCARD)
        return 3;
    else if (flags & REQ_OP_WRITE_SAME)
        return 7;
    else if (flags & REQ_OP_WRITE)
        return 1;
    else
        return 0;
}
#define req_data_dir(flag) (op_is_write(op_from_rq_bits(flag)) ? WRITE : READ)

#endif

int blk_req_start(struct pt_regs *ctx, struct request *req)
{
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
        // bpf_trace_printk("missed tracing issue %d %d \n", _(req->__sector), _(req->__data_len) >> 9);
        return 0;
    }

    bpf_probe_read_str(data.taskid, sizeof(data.taskid), valp->taskid);
    data.io_start_time_ns = _(valp->io_start_time_ns);
    data.latency_ns = bpf_ktime_get_ns() - data.io_start_time_ns;
    start.delete(&req);

	unsigned int cmd_flags = _(req->cmd_flags);
	
    data.opcode = rq_op(cmd_flags);
    data.len = _(req->__data_len) >> SECTOR_SHIFT;
    if(data.len)
    {
        data.slba = _(req->__sector);
    }

    rq_disk = _(req->rq_disk);
    bpf_probe_read_str(data.disk_name, sizeof(data.disk_name), rq_disk->disk_name);
	data.major = _(rq_disk->major);
	data.minor = _(rq_disk->first_minor);
	data.ata_cmd = 0;
	
	if(data.major == 259) {
		struct nvme_command *cmd;
		cmd = _(((struct nvme_request *)(req+1))->cmd);
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
		switch (rq_op(cmd_flags)) {
			case REQ_OP_DRV_IN:
			case REQ_OP_DRV_OUT:
				data.cmnd = _(cmd->common.opcode);	
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
				data.cmnd = (rq_op(cmd_flags) & 1) ? nvme_cmd_write : nvme_cmd_read;
				break;
			default:
				data.cmnd = _(cmd->common.opcode);	
		}
#else
	if (_(req->cmd_type) == REQ_TYPE_DRV_PRIV)
		data.cmnd = _(cmd->common.opcode);	
	else if (cmd_flags & REQ_FLUSH)
		data.cmnd = nvme_cmd_flush;
	else if (cmd_flags & REQ_DISCARD)
		data.cmnd = nvme_cmd_dsm;
	else
		data.cmnd = (req_data_dir(cmd_flags) ? nvme_cmd_write : nvme_cmd_read);
#endif
	}
	else 
	{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
		unsigned char *cmnd = _(((struct scsi_request *)(req+1))->cmd);
		data.cmnd = _(cmnd[0]);
		if( data.opcode == REQ_OP_SCSI_IN || data.opcode == REQ_OP_SCSI_OUT )
#else
		unsigned char *cmnd = _(((struct scsi_cmnd *)req->special)->cmnd);
		data.cmnd = _(cmnd[0]);
		if( data.cmnd == ATA_12 || data.cmnd == ATA_16 || data.opcode > 3 )
#endif
		{
			#define MAX_CDB 32
			unsigned char cdb[MAX_CDB];
#if LINUX_VERSION_CODE >= KERNEL_VERSION(4,15,0)
			unsigned short cmd_len = _(((struct scsi_request *)(req+1))->cmd_len);  
#else
			unsigned short cmd_len = _(((struct scsi_cmnd *)req->special)->cmd_len);
#endif
			int len = cmd_len > MAX_CDB ? MAX_CDB : cmd_len;

			bpf_probe_read(cdb, len, cmnd);	
			scsi_trace_parse_cdb(cdb, &data);
		} 
	}

    events.perf_submit(ctx, &data, sizeof(data));
    // bpf_trace_printk("blk_req_completion %x %x \n", req, data.cmnd);

    return 0;
}
