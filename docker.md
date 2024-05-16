# Docker and container

## Install Docker Engine on CentOS

#### Set up the repository

Install the `yum-utils` package (which provides the `yum-config-manager` utility) and set up the repository.

```bash
$ sudo yum install -y yum-utils
$ sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
```

#### Install Docker Engine

Install the *latest version* of Docker Engine, containerd, and Docker Compose or go to the next step to install a specific version:

```bash
$ sudo yum install docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Start Docker.

```bash
$ sudo systemctl start docker
```



## Manage Docker as a non-root user[🔗](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user)

1. Create the `docker` group.

   ```bash
   $ sudo groupadd docker
   ```

2. Add your user to the `docker` group.

   ```bash
   $ sudo usermod -aG docker $USER
   ```

3. Activate the changes to groups.

   ```bash
   $ newgrp docker
   ```



## Configure Docker to start on boot with systemd

Many modern Linux distributions use [systemd](https://docs.docker.com/config/daemon/systemd/) to manage which services start when the system boots. On Debian and Ubuntu, the Docker service starts on boot by default. To automatically start Docker and containerd on boot for other Linux distributions using systemd, run the following commands:

```bash
$ sudo systemctl enable docker.service
$ sudo systemctl enable containerd.service
```



## WSL2에서 docker demon 자동 실행하기

/etc/sudoers.d/test를 생성 후 아래 내용 추가 

```bash
test ALL=(ALL) NOPASSWD: /usr/bin/dockerd
```

dockerd를 자동 실행 하도록 profile(.bash_aliases) 수정

```bash
echo '# Start Docker daemon automatically when logging in if not running.' >> ~/.bash_aliases
echo 'RUNNING=`ps aux | grep dockerd | grep -v grep`' >> ~/.bash_aliases
echo 'if [ -z "$RUNNING" ]; then' >> ~/.bash_aliases
echo '    sudo dockerd > /dev/null 2>&1 &' >> ~/.bash_aliases
echo '    disown' >> ~/.bash_aliases
echo 'fi' >> ~/.bash_aliases
```



## Accessing the host device inside the container

- Docker 1.2부터 container 실행시 `--device` option을 사용하여 host의 physical device에 접근할 수 있다.

​	--device=host_devname[:container_devname[:permissions]]

```bash
$ docker run --device=<Host Device>:<Container Device Mapping>:<Permissions>   [ OPTIONS ]  IMAGE[:TAG]  [COMMAND]  [ARG...]
```

​	아래는 실행 예시 이다

```bash
$ docker run -it --rm -p 5901:5901 --device=/dev/nvme0n1p2:/dev/nvme0n1p2 ubuntu:19.10
```



- privileaged mode 실행
  docker를 privileaged mode로 실행하게 되면 host의 device들을 container에서 access 가능하다.

```bash
docker run -it --rm -p 5901:5901 --privileged ubuntu:19.10
```



- xwindows 환경을 전달하여 desktop 실행하기

```bash
$ docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix ubuntu:19.10-desktop
```



## Docker에서 'virbr0"에 연결하는 방법

First create the configuration file /etc/docker/daemon.json as suggested in the Docker documentation with the following content (the iptables line may not even be needed):

```json
{
  "bridge": "virbr0",
  "iptables": false
}
```

Than you stop the containers and restart the docker daemon service:

```bash
systemctl restart docker
```



# docker 실행 예시

```bash
docker attach great_heyrovsky      
docker build -t ubuntu:desktop .    
docker commit a58a8b23ad7a ubuntu:19.10-desktop     
docker diff c6968690f279      
docker exec -it 2b80e84ce0bd     
docker info       
docker ps -la      
docker pull tensorflow/tensorflow:latest-jupyter      
docker restart c6968690f279      
docker rm b940f386b22b c28aeb9a03f5 c0f95c0e2796    
docker rmi cc3d42f76456      
docker run -it --link 2fd9060199a5    
docker run -it --rm -p 5901:5901 --mount source=/dev/nvme0n1p2,target=/mnt/nvme,type=bind ubuntu:19.10
docker run -it --rm -p 8888:8888 tensorflow/tensorflow:latest-py3-jupyter  
newgrp docker       
sudo usermod -aG docker $USER    
```



# docker가 실행이 안될때 해결 방법

``` bash
systemctl stop docker
sudo ls -la /var/lib/docker/network/files
sudo rm -rf /var/lib/docker/network
systemctl start docker
systemctl status docker.service
```

