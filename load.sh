#!/bin/bash

pushd ~/linux-4.15.0/drivers/nvme
sudo rmmod nvme
sudo rmmod nvme-core
sudo insmod host/nvme-core.ko streams=1
sudo insmod host/nvme.ko
popd
