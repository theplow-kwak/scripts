#!/bin/bash

getOsVersion()
{
    if [ -f /etc/os-release ]; then
        # freedesktop.org and systemd
        . /etc/os-release
        _OS=$NAME
        _VER=$VERSION_ID
    elif [ -f /etc/lsb-release ]; then
        # For some versions of Debian/Ubuntu without lsb_release command
        . /etc/lsb-release
        _OS=$DISTRIB_ID
        _VER=$DISTRIB_RELEASE
    elif type lsb_release >/dev/null 2>&1; then
        # linuxbase.org
        _OS=$(lsb_release -si)
        _VER=$(lsb_release -sr)
    else
        # Fall back to uname, e.g. "Linux <version>", also works for BSD, etc.
        _OS=$(uname -s)
        _VER=$(uname -r)
    fi
}

getOsVersion
echo $_OS $_VER
