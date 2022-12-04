#!/bin/bash

create_cfgfile()
{
touch $CINIT_FILE

cat <<EOL > $CINIT_FILE
#cloud-config
hostname: $HOST_NAME
users:
  - name: $USER_NAME
    groups: wheel
    lock_passwd: false
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']

ssh_pwauth: false
disable_root: false
runcmd:
  - [ sh, -c, 'touch /etc/cloud/cloud-init.disabled' ]

power_state:
  delay: 'now'
  mode: poweroff
  message: Bye Bye
  timeout: 30
  condition: True
  
final_message: "The system is finally up, after \$UPTIME seconds" 
EOL

if [[ -e $HOME/.ssh/id_rsa.pub ]]; then
    read _SSH_KEY < $HOME/.ssh/id_rsa.pub
    sed -i "/sudo:/ a \    ssh-authorized-keys:\n      - \"${_SSH_KEY}\"" $CINIT_FILE
fi
if [[ -e $_CERT_FILE ]]; then
    printf "\nca-certs:\n  trusted:\n  - |\n" >> $CINIT_FILE
    cat $_CERT_FILE >> $CINIT_FILE
fi
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] 

Options:
 -n, --name <NAME>          set the login USER name
 -H, --host <HOST_NAME>     set the HOST name
 -f, --fname <FILE_NAME>    set the cloud_init file name
EOM
}

options=$(getopt -n ${0##*/} -o n:H:f:c:h \
                --long name:,host:,fname:,cert:,help -- "$@")
[ $? -eq 0 ] || { 
    usage
    exit 1
}
eval set -- "$options"

while true; do
    case "$1" in
        -n | --name )   USER_NAME=$2 ;      shift ;;    # set login user name
        -H | --host )   HOST_NAME=$2 ;      shift ;;    
        -f | --fname )  CINIT_FILE=$2 ;     shift ;;
        -c | --cert )   _CERT_FILE=$2 ;     shift ;;
        -h | --help )   usage ;             exit ;;
        --)             shift ;             break ;;
    esac
    shift
done 

_TMP=$(echo $RANDOM|md5sum|sed 's/^\(....\).*$/\U\1/')
USER_NAME=${USER_NAME:-$USER}
HOST_NAME=${HOST_NAME:-"${USER_NAME}-QEMU-${_TMP}"}
CINIT_FILE=${CINIT_FILE:-"_cloud_init.cfg"}

[[ -e $HOME/.ssh/id_rsa.pub ]] || ssh-keygen -t rsa

create_cfgfile
cloud-localds -v cloud_init.iso $CINIT_FILE

