#!/bin/sh

_br=br0

if ! [ -d /sys/class/net/$_br ]; then
    _eth=$(ip addr show | awk '/inet.*brd/{print $NF}')
    _eth_name=$(nmcli -t -f NAME,TYPE,DEVICE con show | awk -F: '$2 ~ /.*ethernet/ {print $1}')

    nmcli connection add type bridge ifname $_br con-name $_br stp no
    nmcli connection add type bridge-slave ifname $_eth master $_br
    nmcli connection down "$_eth_name"
    nmcli connection up $_br
#    nmcli connection add type tun ifname $_tap con-name $_tap mod tap owner `id -u`
#    nmcli connection add type bridge-slave ifname $_tap master $_br
else
    _br_slave=$(nmcli -t -f NAME,TYPE,DEVICE con show | awk -F: '$1 ~ /bridge.*/ {print $1}')
    nmcli connection down $_br_slave
    nmcli connection down $_br
    sleep .5
    nmcli con del $_br_slave
    nmcli con del $_br

    _eth_name=$(nmcli -t -f NAME,TYPE,DEVICE con show | awk -F: '$2 ~ /.*ethernet/ {print $1}')
    nmcli con up "$_eth_name"
fi
