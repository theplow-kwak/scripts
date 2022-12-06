#!/bin/bash

runshell()
{
    cmd=$1
    echo "runshell: ${cmd[*]}"
    ret_stdout=$(${cmd[@]})
    retcode=$?
    echo "runshell return code: $retcode, stdout: $ret_stdout"
    echo " "
    return $retcode
}

result=$(runshell "virsh --quiet net-dhcp-leases default")
SAVEIFS=$IFS; IFS=$'\n'; dhcp_leases=($result); IFS=$SAVEIFS

if [[ ${#dhcp_leases[@]} > 0 && $1 ]]; then
    dhcp_info=(${dhcp_leases[$1]})
    mac=${dhcp_info[2]}
    localip=${dhcp_info[4]%/*}
    name=${dhcp_info[5]}
    dest_str="<host mac='$mac' name='$name' ip='$localip' />"
    echo "virsh net-update default delete ip-dhcp-host \"$dest_str\" --live --config"
    (virsh net-update default delete ip-dhcp-host "$dest_str" --live --config)
else
    for dhcp in "${dhcp_leases[@]}"; do
        echo "${dhcp}"
    done
fi

SSHPORT=${1:-5900}
SPICEPORT=$(($SSHPORT+1))

while (runshell "lsof -w -i :$SPICEPORT") || (runshell "lsof -w -i :$SSHPORT"); do 
    echo "increase port number: $SSHPORT"
    SSHPORT=$(($SSHPORT+2))
    SPICEPORT=$(($SSHPORT+1)); done 

echo "final port number: $SSHPORT, $SPICEPORT"
