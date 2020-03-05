#!/bin/sh

_br=br0
_eth=$(ip addr show | awk '/inet.*brd/{print $NF}')
_eth_name=$(nmcli -t -f NAME,TYPE,DEVICE con show | awk -F: '$2 ~ /.*ethernet/ {print $1}')

sudo nmcli connection add type bridge ifname $_br con-name $_br stp no
sudo nmcli connection add type bridge-slave ifname $__eth master $_br
sudo nmcli connection down $_eth_name
sudo nmcli connection up $_br

sudo nmcli connection add type tun ifname $_tap con-name $_tap mod tap owner `id -u`
sudo nmcli connection add type bridge-slave ifname $_tap master $_br

