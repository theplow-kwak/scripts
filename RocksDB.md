
# RocksDB 
- Dependencies

```bash
sudo apt-get install libgflags-dev
sudo apt-get install libsnappy-dev
sudo apt-get install zlib1g-dev
sudo apt-get install libbz2-dev
sudo apt-get install liblz4-dev
sudo apt-get install libzstd-dev
```
- clone RocksDB

```bash
git clone https://github.com/facebook/rocksdb
git checkout v5.14.2
```

## Add debug information for stream allocation to env/io_posix.cc
```
#ifdef OS_LINUX
// Suppress Valgrind "Unimplemented functionality" error.
#ifndef ROCKSDB_VALGRIND_RUN
  fprintf(stdout, "  SetWriteLifeTimeHint: %s   Write hint: %d \n", filename_.c_str(), hint);
```

## static build 
```bash
export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64/"
make jclean
make -j12 rocksdbjavastatic -e DISABLE_WARNING_AS_ERROR=ON
mvn install:install-file -Dfile=java/target/rocksdbjni-5.16.0-linux64.jar -Dversion=5.16.0 -DgroupId=org.rocksdb -DartifactId=rocksdbjni -Dpackaging=jar
```

## debug build
```bash
export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64/"
make jclean
make -j8 rocksdbjava
mvn install:install-file -Dfile=java/target/rocksdbjni-5.13.0-linux64.jar -Dversion=5.13.0 -DgroupId=org.rocksdb -DartifactId=rocksdbjni -Dpackaging=jar
```

## full build
```bash
export JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64/"

make clean
make all
```