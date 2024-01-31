#!/bin/bash

systemctl stop mysql
systemctl stop apparmor

export SOURCEDIR="/var/lib/mysql"
export TARGETDIR="/mnt/gemini/mysql"

sudo cp -rv $SOURCEDIR $TARGETDIR
sudo chown -R mysql:mysql $TARGETDIR
sudo mv $SOURCEDIR $SOURCEDIR.old
sudo ln -s $TARGETDIR $SOURCEDIR 
sudo chown -R mysql:mysql $SOURCEDIR

sudo cp /etc/mysql/mysql.conf.d/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf.old
sudo cp /etc/apparmor.d/usr.sbin.mysqld /etc/apparmor.d/usr.sbin.mysqld.old
sudo sed -i -e "s|$SOURCEDIR|$TARGETDIR|" /etc/mysql/mysql.conf.d/mysqld.cnf
sudo sed -i -e "s|$SOURCEDIR|$TARGETDIR|" /etc/apparmor.d/usr.sbin.mysqld
sudo sh -c 'echo "alias $SOURCEDIR/ -> $TARGETDIR/," >> /etc/apparmor.d/tunables/alias'
sudo mkdir $SOURCEDIR/mysql -p

systemctl start apparmor
systemctl start mysql
