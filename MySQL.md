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

## modify debian/rules
```
    :
		-DCOMPILATION_COMMENT="($(DISTRIBUTION))" \
		-DMYSQL_SERVER_SUFFIX="-nvme" \
		-DINSTALL_MYSQLDATADIR="/mnt/nvme/mysql" \
		-DINSTALL_LAYOUT=DEB \
    :
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
sudo cp -rv /var/lib/mysql /mnt/nvme/mysql
sudo chown -R mysql:mysql /mnt/nvme/mysql
sudo mv /var/lib/mysql /var/lib/mysql.old
sudo ln -s /mnt/nvme/mysql /var/lib/mysql 
sudo chown -R mysql:mysql /var/lib/mysql
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

