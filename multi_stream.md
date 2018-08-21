
# iol_interact-8.0 
```bash
sudo apt-get install runit
sudo apt-get install libxml++2.6-dev 
sudo apt-get install libboost-all-dev
sudo apt-get install doxygen
sudo apt-get install linux-headers-$(uname -r)
```
dnvme.ko build시에 gcc version이 맞지 않으면 insmod에서 error 발생 (kernel patch와 연관) -> ppa:ubuntu-toolchain-r/test 사용하면 안됨


# install tools 
```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev 
sudo apt install python python3 python-pip python3-pip python-tk bison
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant
```


# RocksDB 
- clone RocksDB  
```bash
git clone https://github.com/facebook/rocksdb
git checkout v5.14.2

export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64/"

make clean
make all
```

env/io_posix.cc
```
#ifdef OS_LINUX
// Suppress Valgrind "Unimplemented functionality" error.
#ifndef ROCKSDB_VALGRIND_RUN
  fprintf(stdout, "  SetWriteLifeTimeHint: %s   Write hint: %d \n", filename_.c_str(), hint);
```

## static build 
```bash
make jclean
make -j8 rocksdbjavastatic
mvn install:install-file -Dfile=java/target/rocksdbjni-5.14.2-linux64.jar -Dversion=5.14.2 -DgroupId=org.rocksdb -DartifactId=rocksdbjni -Dpackaging=jar
```

## debug build
```bash
make jclean
make -j8 rocksdbjava
mvn install:install-file -Dfile=java/target/rocksdbjni-5.13.0-linux64.jar -Dversion=5.13.0 -DgroupId=org.rocksdb -DartifactId=rocksdbjni -Dpackaging=jar
```



# YCSB 
## clone YCSB source
```bash
git clone https://github.com/brianfrankcooper/YCSB ycsb 
git checkout 0.14.0
```

## ycsb for RocksDB
### patch RocksDB binding
```bash
git remote add adamretter https://github.com/adamretter/YCSB
git branch rocksdb
git checkout rocksdb
git merge remotes/adamretter/rocks-java
```

### patch use local RocksDB build -
```
>> build rocksdb and maven install to ~/.m2/repository/org/rocksdb/rocksdbjni
>> modify pom.xml
-    <rocksdb.version>5.11.3</rocksdb.version>
+    <rocksdb.version>5.13.0</rocksdb.version>    << version of local RocksDB 

sed -i s/5.11.3/5.14.2/ pom.xml
```

### build 
```bash
mvn clean package  << full build 
mvn -pl com.yahoo.ycsb:rocksdb-binding -am clean package
```

### run YCSB -
```bash
./bin/ycsb load rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data 
./bin/ycsb run rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data 

./bin/ycsb load rocksdb -s -P workloads/workloadf -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data 
./bin/ycsb run rocksdb -s -P workloads/workloadf -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data 

./bin/ycsb load rockdb -P workloads/workloada -P large.dat -s -threads 10 -target 100 -p measurementtype=timeseries -p timeseries.granularity=2000 > transactions.dat
```

## ycsb for MySQL
ycsb를 사용하여 MySQL test를 진행 할 수 있도록 환경 구축


### jdbc compile
- add dependency information into the pom file (ycsb/jdbc/pom.xml)
```
<dependency>
    <groupId>mysql</groupId>
    <artifactId>mysql-connector-java</artifactId>
    <version>5.1.46</version>
</dependency>
```
- maven compile
```
mvn -pl com.yahoo.ycsb:jdbc-binding -am clean package
```

### Configure database and table
- Create a new database, for example ycsb
```
$ mysql -u root -h 127.0.0.1

mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| dbt2               |
| my_wiki            |
| mysql              |
| performance_schema |
| sys                |
+--------------------+
6 rows in set (0.00 sec)

mysql> create database ycsb;
Query OK, 1 row affected (0.01 sec)

mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| dbt2               |
| my_wiki            |
| mysql              |
| performance_schema |
| sys                |
| ycsb               |
+--------------------+
7 rows in set (0.00 sec)

mysql> exit;
Bye
```

- and create the "usertable" table with the sql script 

mysql/create_table.mysql:

```
DROP TABLE IF EXISTS usertable;

-- Create the user table with 5 fields.
CREATE TABLE usertable(YCSB_KEY VARCHAR (255) PRIMARY KEY,
  FIELD0 TEXT, FIELD1 TEXT,
  FIELD2 TEXT, FIELD3 TEXT,
  FIELD4 TEXT, FIELD5 TEXT,
  FIELD6 TEXT, FIELD7 TEXT,
  FIELD8 TEXT, FIELD9 TEXT);
```
```
$ mysql -u root -h 127.0.0.1 -D ycsb < mysql/create_table.mysql
```
- confirm database and usertable

```
$ mysql -u root -h 127.0.0.1 -D ycsb

mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| dbt2               |
| my_wiki            |
| mysql              |
| performance_schema |
| sys                |
| ycsb               |
+--------------------+
7 rows in set (0.00 sec)

mysql> use ycsb;
Database changed
mysql> show tables;
+----------------+
| Tables_in_ycsb |
+----------------+
| usertable      |
+----------------+
1 row in set (0.00 sec)

mysql> exit;
Bye
```

### workloads/mysql
```
workload=com.yahoo.ycsb.workloads.CoreWorkload

operationcount=150000

table=usertable
writetable=text_for_write

fieldnames=YCSB_KEY,FIELD0,FIELD1,FIELD2,FIELD3,FIELD4,FIELD5,FIELD6,FIELD7,FIELD8,FIELD8
primarykey=YCSB_KEY

writerate=0.05
mysql.upsert=true

jdbc.driver=com.mysql.jdbc.Driver
db.url=jdbc:mysql://127.0.0.1:3306/ycsb
db.user=root
db.passwd=
```
### Load some data
```bash
bin/ycsb load jdbc -P workloads/mysql
```
### Run the stress test
```bash
bin/ycsb run jdbc -P workloads/mysql -s -threads 32
```


# kernel tracing on ubuntu
> https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel#Obtaining_the_source_for_an_Ubuntu_release

## get kernel source 
```bash
sudo apt install ncurses-dev
apt source linux-headers-$(uname -r)
sudo apt build-dep linux-headers-$(uname -r)
```

## kernel tracing patch
download nvme_driver.diff to ~/
```bash
cd ~/linux-4.15.0
patch -p1 < ../nvme_driver.diff

diff -urN nvme_u1804_org/drivers/nvme linux-4.15.0/drivers/nvme > nvme_driver.diff
```

## build NVMe module driver 
> https://wiki.ubuntu.com/KernelCustomBuild

```bash
cd drivers/nvme
make -C /lib/modules/`uname -r`/build M=`pwd` modules
sudo make -C /lib/modules/`uname -r`/build M=`pwd` modules_install install

#make M=./drivers/nvme modules
#sudo make M=./drivers/nvme modules_install install

sudo depmod -a
```

## build kernel 
```bash
fakeroot debian/rules clean
(fakeroot debian/rules editconfigs) 
debian/rules build
fakeroot debian/rules binary-headers binary-generic binary-perarch
```

## enable kernel trace  
```bash
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
sudo cat /sys/kernel/debug/tracing/trace_pipe | tee ./nvme.log
```

# nvme-cli
```bash
sudo nvme id-ctrl /dev/nvme0
sudo nvme dir-receive /dev/nvme0 -D 1 -O 1 -H
sudo nvme smart-log /dev/nvme0
```

# bcc 
```bash
sudo apt install cmake clang libedit-dev llvm libclang-dev luajit libfl-dev
sudo apt install luajit luajit-5.1-dev
sudo apt install netperf iperf 

git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_CMD=python3
make
sudo make install
```

# MySQL Build 
## Installing MySQL from Source with the MySQL APT Repository
> https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/#repo-qp-apt-install-from-source

You can download the source code for MySQL and build it using the MySQL APT Repository:
```bash
sudo apt-get update
sudo apt-get build-dep mysql-server
sudo apt-get install mysql-common
apt-get source mysql-server
```

## modify cmake/install_layout.cmake
```
   :
#
# DEB layout
#
   :
#
SET(INSTALL_MYSQLDATADIR_DEB            "/mnt/nvme/mysql")
```

## build mysql-server
```bash
apt-get source -b mysql-server
```
deb packages for installing the various MySQL components are created.

## install deb package
Pick the deb packages for the MySQL components you need and install them with the command:
```
sudo dpkg-preconfigure mysql-client-core-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i mysql-client-core-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg-preconfigure mysql-client-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i mysql-client-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb

sudo dpkg-preconfigure mysql-server-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i mysql-server-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg-preconfigure mysql-server-core-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i mysql-server-core-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb

sudo dpkg-preconfigure libmysqlclient-dev_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i libmysqlclient-dev_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg-preconfigure libmysqlclient20_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i libmysqlclient20_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg-preconfigure libmysqld-dev_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i libmysqld-dev_5.7.23-0ubuntu0.18.04.1_amd64.deb

sudo dpkg-preconfigure mysql-client_5.7.23-0ubuntu0.18.04.1_all.deb
sudo dpkg -i mysql-client_5.7.23-0ubuntu0.18.04.1_all.deb
sudo dpkg-preconfigure mysql-server_5.7.23-0ubuntu0.18.04.1_all.deb
sudo dpkg -i mysql-server_5.7.23-0ubuntu0.18.04.1_all.deb
sudo dpkg-preconfigure mysql-source-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
sudo dpkg -i mysql-source-5.7_5.7.23-0ubuntu0.18.04.1_amd64.deb
```

cmake . -DBUILD_CONFIG=mysql_release -DMYSQL_DATADIR=/mnt/nvme/mysql/ -DIGNORE_AIO_CHECK=1
cmake . -DBUILD_CONFIG=mysql_release -DMYSQL_DATADIR=/mnt/nvme/mysql/ -DCMAKE_INSTALL_PREFIX=/usr/bin/

## custom build from generic source
### Preconfiguration setup
```bash
sudo groupadd mysql
sudo useradd -r -g mysql -s /bin/false mysql
```

### Beginning of source-build specific instructions
```
( test -d builddir || mkdir builddir ) && cd builddir && \
sh -c  'PATH=${MYSQL_BUILD_PATH:-"/bin:/usr/bin"} \
	CC=${MYSQL_BUILD_CC:-gcc} \
	CXX=${MYSQL_BUILD_CXX:-g++} \
	cmake -DCMAKE_INSTALL_PREFIX=/usr \
	-DCMAKE_VERBOSE_MAKEFILE=ON \
	-DMYSQL_UNIX_ADDR=/var/run/mysqld/mysqld.sock \
	-DCMAKE_BUILD_TYPE=RelWithDebInfo \
	-DBUILD_CONFIG=mysql_release \
	-DWITH_LIBWRAP=ON \
	-DWITH_ZLIB=system \
	-DWITH_LZ4=system \
	-DWITH_EDITLINE=system \
	-DWITH_LIBEVENT=system \
	-DWITH_SSL=bundled \
	-DWITH_BOOST=../boost \
	-DCOMPILATION_COMMENT="(Ubuntu)" \
	-DMYSQL_SERVER_SUFFIX="-nvme" \
	-DINSTALL_LAYOUT=DEB \
	-DINSTALL_DOCDIR=share/mysql/docs \
	-DINSTALL_DOCREADMEDIR=share/mysql \
	-DINSTALL_INCLUDEDIR=include/mysql \
	-DINSTALL_INFODIR=share/mysql/docs \
	-DINSTALL_LIBDIR=lib/x86_64-linux-gnu \
	-DINSTALL_MANDIR=share/man \
	-DINSTALL_MYSQLSHAREDIR=share/mysql \
	-DINSTALL_MYSQLTESTDIR=lib/mysql-test \
	-DINSTALL_PLUGINDIR=lib/mysql/plugin \
	-DINSTALL_SBINDIR=sbin \
	-DINSTALL_SCRIPTDIR=bin \
	-DINSTALL_SUPPORTFILESDIR=share/mysql \
	-DSYSCONFDIR=/etc/mysql \
	-DWITH_EMBEDDED_SERVER=ON \
	-DWITH_ARCHIVE_STORAGE_ENGINE=ON \
	-DWITH_BLACKHOLE_STORAGE_ENGINE=ON \
	-DWITH_FEDERATED_STORAGE_ENGINE=ON \
	-DWITH_INNODB_MEMCACHED=1 \
	-DINSTALL_MYSQLDATADIR="/mnt/nvme/mysql" \
	-DWITH_EXTRA_CHARSETS=all ..'
```

```
make -j8
sudo make install
```

### Postinstallation setup
```
sudo mkdir /var/lib/mysql-files
sudo chown mysql:mysql /var/lib/mysql-files
sudo chmod 750 /var/lib/mysql-files
mysqld --initialize --user=mysql 
mysql_ssl_rsa_setup
mysqld_safe --user=mysql &

```

# MySQL datadir change 
> http://ourcstory.tistory.com/134

## datadir 확인
```bash
$ sudo mysql -u root
```
```
mysql> USE mysql;
mysql> show variables like 'datadir'; 
+---------------+-----------------+
| Variable_name | Value           |
+---------------+-----------------+
| datadir       | /var/lib/mysql/ |
+---------------+-----------------+
```

## Change datadir
1. stop mysql server
```bash
systemctl stop mysql
systemctl stop apparmor
```
2. Move data to a new location
```bash
sudo rsync -rv /var/lib/mysql /mnt/nvme/mysql
sudo chown -R mysql:mysql /mnt/nvme/mysql
```
3. Modify the configuration file.
```bash
sudo cp /etc/mysql/mysql.conf.d/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf.old
sudo cp /etc/apparmor.d/usr.sbin.mysqld /etc/apparmor.d/usr.sbin.mysqld.old
sudo sed -i -e 's/\/var\/lib\/mysql/\/mnt\/nvme\/mysql/' /etc/mysql/mysql.conf.d/mysqld.cnf
sudo sed -i -e 's/\/var\/lib\/mysql\//\/mnt\/nvme\/mysql\//' /etc/apparmor.d/usr.sbin.mysqld
sudo sh -c 'echo "alias /var/lib/mysql/ -> /mnt/nvme/mysql/," >> /etc/apparmor.d/tunables/alias'
sudo mkdir /var/lib/mysql/mysql -p
```
4. restart the server
```bash
systemctl start apparmor
systemctl start mysql
```

```
SUDO_EDITOR=kate sudoedit /etc/mysql/mysql.conf.d/mysqld.cnf  :  
  [mysqld]
  datadir		= /mnt/nvme/mysql

/etc/apparmor.d/usr.sbin.mysqld  : 
# Allow data dir access
  /mnt/nvme/mysql/ r,
  /mnt/nvme/mysql/** rwk,
```

> https://www.digitalocean.com/community/tutorials/how-to-move-a-mysql-data-directory-to-a-new-location-on-ubuntu-16-04

# How to reinstall MySQL
## First remove MySQL
```
sudo apt-get remove --purge mysql-server mysql-client mysql-common
sudo apt-get autoremove
sudo apt-get autoclean
```
## Then reinstall:
```
sudo apt-get update
sudo apt-get install mysql-common
sudo mysql_install_db
sudo /usr/bin/mysql_secure_installation
```

# DBT2 MySQL benchmarke
## Download source
> https://dev.mysql.com/downloads/benchmarks.html

## build dbt2
```bash
./configure --with-mysql
make
```

## Running dbt2
### Data generation and loading:
```bash
mkdir /mnt/nvme/dbt2
./src/datagen -w 30 -d /mnt/nvme/dbt2 --mysql
```

### fix Access denied for user 'root'@'localhost'
> https://stackoverflow.com/questions/39281594/error-1698-28000-access-denied-for-user-rootlocalhost

```
$ sudo mysql -u root 
mysql> USE mysql;
mysql> SELECT User, Host, plugin FROM mysql.user;
mysql> UPDATE user SET plugin='mysql_native_password' WHERE User='root';
mysql> FLUSH PRIVILEGES;
mysql> exit;

$ systemctl restart mysql
```

### Loading the data into the database...
```
./scripts/mysql/mysql_load_db.sh --path /mnt/nvme/dbt2 --local --mysql-path $(which mysql) 
```
### Loading the stored procedures...
```
./scripts/mysql/mysql_load_sp.sh --client-path $(dirname $(which mysql)) --sp-path storedproc/mysql 
```
### Running the benchmark...
```
./scripts/run_mysql.sh --connections 20 --time 300 --warehouses 30 --zero-delay 
```

> http://brtech.tistory.com/57 


# fio test
```bash
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randrw --rwmixread=75
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randread 
```

# vmdk to vhdx
```
ConvertTo-MvmcVirtualHardDisk -SourceLiteralPath "D:\VMPC\Ubuntu 1804 64-bit\Ubuntu 1804 64-bit.vmdk" -DestinationLiteralPath u1804 -VhdType DynamicHarddisk -VhdFormat vhdx
```

# How to do Screen Sharing on Ubuntu 18.04

Now you need to install dconf-editor with this command:

sudo apt-get install dconf-editor

Now open a terminal and type

dconf-editor

Now navigate to:

ORG > GNOME > DESKTOP > REMOTE ACCESS

Then find the “Require Encryption” setting and toggle it off
Now you can open your favorite VNC client and view your remote screen!
