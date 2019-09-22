# Docker and container



## Accessing the host device inside the container

Docker 1.2부터 container 실행시 `--device` option을 사용하여 host의 physical device에 접근할 수 있다.

```bash
$ docker run --device=<Host Device>:<Container Device Mapping>:<Permissions>   [ OPTIONS ]  IMAGE[:TAG]  [COMMAND]  [ARG...]
```

아래는 실행 예시 이다

```bash
$ docker run -it --rm -p 5901:5901 --device=/dev/nvme0n1p2:/dev/nvme0n1p2 ubuntu:19.10
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

