#!/bin/bash

create_cfgfile()
{
    touch $CINIT_FILE

cat <<EOL > $CINIT_FILE
#cloud-config

preserve_hostname: false
hostname: $HOST_NAME
fqdn: ${HOST_NAME}.lo

users:
  - name: $USER_NAME
    lock_passwd: false
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']

chpasswd:
  users:
    - name: root
      password: Passw0rd
      type: text
    - name: $USER_NAME
      password: qwerasdf
      type: text
  expire: False

write_files:
  - path: /etc/netplan/01-network-all.yaml
    owner: root:root
    permissions: '0600'
    content: |-
      network:
        version: 2
        ethernets:
          id0:
            match:
              name: "en*"
            dhcp4: true
       

ssh_pwauth: false
disable_root: false
runcmd:
  - [ sh, -c, 'touch /etc/cloud/cloud-init.disabled' ]
  - mkdir /mnt/host

mounts:
  - [ hostfs, /mnt/host, virtiofs ]

mount_default_fields: [ None, None, "auto", "defaults,nofail", "0", "2" ]

power_state:
  delay: 'now'
  mode: poweroff
  message: Bye Bye
  timeout: 30
  condition: True

EOL

    [[ -e $HOME/.ssh/id_rsa.pub ]] || ssh-keygen -t rsa
    if [[ -e $HOME/.ssh/id_rsa.pub ]]; then
        read _SSH_KEY < $HOME/.ssh/id_rsa.pub
        sed -i "/sudo:/ a \    ssh-authorized-keys:\n      - \"${_SSH_KEY}\"" $CINIT_FILE
    fi
    if [[ $_CERT_FILE ]]; then
        printf "ca_certs:\n  trusted:\n" >> $CINIT_FILE
        for _FILE in ${_CERT_FILE[@]};
        do
        printf "    - |\n" >> $CINIT_FILE
        cat $_FILE >> $CINIT_FILE
        done
        printf "\n" >> $CINIT_FILE
    fi

    printf "final_message: \"The system is finally up, after \$UPTIME seconds\"\n" >> $CINIT_FILE
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] 

Options:
 -u, --uname <NAME>         The login USER name
 -H, --host <HOST_NAME>     Set the HOST name
 -b, --backing <BACKIMG>    qemu image backing file
 -i, --image <IMGNAME>      qemu image name
 -n, --net <NET>            qemu Network interface model
 -k, --kernel <KERNEL>      Set the custom kernel 
 -f, --fname <FILE_NAME>    The cloud_init file name (default:"_cloud_init.cfg")
EOM
}

set_args()
{
    options=$(getopt -n ${0##*/} -o u:H:f:c:hb:i:q:n:k: \
                    --long uname:,host:,fname:,cert:,backing:,image:,qemu:,net:,kernel:,help -- "$@")
    [ $? -eq 0 ] || { 
        usage
        exit 1
    }
    eval set -- "$options"

    while true; do
        case "$1" in
            -b | --backing)     BACKIMG=$2 ;        shift ;;
            -i | --image)       IMGNAME=$2 ;        shift ;;
            -q | --qemu)        QEMU=$2 ;           shift ;;	
            -n | --net)         NET=$2 ;            shift ;;
            -k | --kernel)		KERNEL=$2 ;         shift ;;
            -u | --uname )      USER_NAME=$2 ;      shift ;;    # set login user name
            -H | --host )       HOST_NAME=$2 ;      shift ;;    
            -f | --fname )      CINIT_FILE=$2 ;     shift ;;
            -c | --cert )       _CERT_FILE+=(${2//,/ }) ;     shift ;;
            -h | --help )       usage ;             exit ;;
            --)                 shift ;             break ;;
        esac
        shift
    done 

    BACKIMG=${BACKIMG:-"../cd/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2"}
    IMGNAME=${IMGNAME:-"${PWD##*/}.qcow2"}
    QEMU=${QEMU:-"qemu"}
    NET=${NET:-"bridge"}

    _TMP=$(echo -n ${IMGNAME} | md5sum)
    USER_NAME=${USER_NAME:-$USER}
    HOST_NAME=${HOST_NAME:-"${IMGNAME%.*}-VM-${_TMP::2}"}
    CINIT_FILE=${CINIT_FILE:-"_cloud_init.cfg"}

    OPTIONS=$@
}

set_args $@

if [[ ! -e $IMGNAME ]]; then
    create_cfgfile
    cloud-localds -v cloud_init.iso $CINIT_FILE
    qemu-img create -f qcow2 $IMGNAME -F qcow2 -b $BACKIMG
    qemu-img resize $IMGNAME 30G
    CLOUD_INIT="cloud_init.iso"
fi

[[ -n $KERNEL ]] && KERNEL="--kernel $(realpath ~/projects/${KERNEL}/arch/x86_64/boot/bzImage)"

if [[ -e $IMGNAME ]]; then
    _CMD=($QEMU --bios --connect ssh --net $NET --uname $USER_NAME $KERNEL $IMGNAME $CLOUD_INIT $OPTIONS)
    echo "${_CMD[@]}"
    ${_CMD[@]}
fi
