#!/bin/bash

pushd ~/linux-4.15.0/drivers/nvme
make -C /lib/modules/`uname -r`/build M=`pwd` clean modules
popd
