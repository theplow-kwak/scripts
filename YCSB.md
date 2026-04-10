
# YCSB 
## 환경 설정

* ycsb 실행에 필요한 tool과 library를 설치한다.

```bash
sudo apt install maven
sudo apt install openjdk-8-jdk
```

* ssl 인증 오류로 인하여 https를 사용하는 repository에서 library를 다운로드 하지 못하는 경우 인증서를 Java cacerts keystore에 추가한다.  

```bash
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64/
sudo keytool -import -trustcacerts -storepass changeit -noprompt -keystore ${JAVA_HOME}/jre/lib/security/cacerts -file /usr/share/ca-certificates/mozilla/cert.crt
```

* 인증서가 제대로 추가되었는지 확인

```bash
keytool -list -keystore ${JAVA_HOME}/jre/lib/security/cacerts
```

* 인증서 삭제가 필요한 경우

```bash
keytool -delete  -alias letsencrypt -keystore ${JAVA_HOME}/jre/lib/security/cacerts -storepass changeit
```



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
../ycsb/bin/ycsb load rocksdb -s -P workloads/nvme_test -p rocksdb.dir=/media/dhkwak/nvme/ycsb-rocksdb-data
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
```bash
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

apparmor (and selinux) provide additional access controls beyond permissions that can cause these permission denied (13) errors. This occurs generally on systems where data or log files differ from the default.

With apparmor you would add to the bottom of /etc/apparmor.d/local/usr.sbin.mysqld:
/mnt/gemini/mysql/ r,
/mnt/gemini/mysql/** rwk, 

And then reload the apparmor service:
```
service apparmor reload 
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
  FIELD8 TEXT, FIELD9 TEXT) DATA DIRECTORY = '/mnt/gemeni/mysql/ycsb';
```

```bash
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

mysql> SHOW VARIABLES LIKE 'innodb_file_per_table';

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

