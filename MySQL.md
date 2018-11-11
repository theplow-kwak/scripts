# MySQL Build 
MySQL Source code에 NVMe multi-stream feature를 적용하여 설치하는 방법을 설명합니다. MySQL document중 [A Quick Guide to Using the MySQL APT Repository](https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/#repo-qp-apt-install-from-source) 를 참조하였습니다.  

## Download source code

You can download the source code for MySQL and build it using the MySQL APT Repository:
```bash
sudo apt-get update
sudo apt-get build-dep mysql-server
sudo apt-get install mysql-common
apt-get source mysql-server
```



## Modify debian/rules

source code build후 생성되는 **.deb ** file의 prefix와 **DATADIR**을 변경하기 위하여 ***debian/rules*** file 수정. 

```
    :
		-DCOMPILATION_COMMENT="($(DISTRIBUTION))" \
		-DMYSQL_SERVER_SUFFIX="-nvme" \
		-DINSTALL_MYSQLDATADIR="/mnt/nvme/mysql" \
		-DINSTALL_LAYOUT=DEB \
    :
```



## NVMe Multi stream 적용 

MySQL + InnoDB application에 multi stream 적용: InnoDB storage engine의 file handling code중 file open 부분에서 file type에 따라 write_hint를 지정하는 방식으로 수정한다.  

InnoDB에서 사용하는 file type은 **OS_LOG_FILE**, **OS_DATA_FILE**, **OS_DATA_TEMPFILE** 세가지가 있다. 

```
/** Types for file create @{ */
static const ulint OS_DATA_FILE = 100;
static const ulint OS_LOG_FILE = 101;
static const ulint OS_DATA_TEMP_FILE = 102;
```

InnoDB의 File open을 처리하는 code에 file type에 따라 stream을 할당하는 code 추가: 

- file : `mysql/storage/innobase/os/os0file.cc`

- function: `os_file_create_func`

```c
} while (retry);

ulint		write_hint = (((type-100)%4)+3);

if(file.m_file != -1) {
    if( fcntl(file.m_file, F_SET_RW_HINT, &write_hint ) != 0 ) {
        ib::error()
            << "stream allocation error: (" << errno << ") "
            << name << " type " << type << " hint " <<  write_hint;
        ib::error()
            << "file create mode "
            << create_mode << " for file '" << name << "'";
    } else {
        ib::info()
            << "stream allocation: "
            << name << " type " << type << " hint " <<  write_hint;
    }
}

/* We disable OS caching (O_DIRECT) only on data files */

if (!read_only
```


## Build mysql-server

```bash
apt-get source -b mysql-server
```
deb packages for installing the various MySQL components are created.

## Install deb package
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

## debian build
```bash
fakeroot debian/rules clean
debian/rules build
DEB_BUILD_OPTIONS=parallel=12 AUTOBUILD=1 fakeroot debian/rules binary
```

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
	-DWITH_SYSTEMD=1 \
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
export SOURCEDIR="/var/lib/mysql"
export TARGETDIR="/mnt/gemini/mysql"

sudo cp -rv $SOURCEDIR $TARGETDIR
sudo chown -R mysql:mysql $TARGETDIR
sudo mv $SOURCEDIR $SOURCEDIR.old
sudo ln -s $TARGETDIR $SOURCEDIR 
sudo chown -R mysql:mysql $SOURCEDIR
```

3. Modify the configuration file.
```bash
sudo cp /etc/mysql/mysql.conf.d/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf.old
sudo cp /etc/apparmor.d/usr.sbin.mysqld /etc/apparmor.d/usr.sbin.mysqld.old
sudo sed -i -e "s|$SOURCEDIR|$TARGETDIR|" /etc/mysql/mysql.conf.d/mysqld.cnf
sudo sed -i -e "s|$SOURCEDIR|$TARGETDIR|" /etc/apparmor.d/usr.sbin.mysqld
sudo sh -c 'echo "alias $SOURCEDIR/ -> $TARGETDIR/," >> /etc/apparmor.d/tunables/alias'
sudo mkdir $SOURCEDIR/mysql -p
```

4. restart the server
```bash
systemctl start apparmor
systemctl start mysql
```
status check
```
journalctl -xe -u mysql
journalctl -xe -u apparmor
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
https://downloads.mysql.com/source/dbt2-0.37.50.15.tar.gz

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

