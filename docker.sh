#!/bin/bash

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] dockerimage

Options:
 -d, --docker   Name of the docker image
 -n, --nvmecli  use nvme-cli source

EOM
}

options=$(getopt -n ${0##*/} -o nd: \
                --long help,docker:,nvmecli -- "$@")
[ $? -eq 0 ] || { usage; exit 1; }
eval set -- "$options"

while true; do
    case $1 in
        -d | --docker )     DOCKERNAME=${2} ;        shift ;;
        -n | --nvmecli )    NVMECLI="true" ;;
        -h | --help )       usage ;                 exit ;;
        --)                 shift ;                 break ;;
    esac
    shift
done 

DOCKERNAME=${1:-"nvmecli_amd64"}

if [[ -n $NVMECLI ]] ;
then  
    SRC_PATH="$HOME/projects/nvme-cli"
    CONTAINER="${DOCKERNAME}_cont"
fi

DOCKERFILE="${SRC_PATH}/docker/${DOCKERNAME}/"
echo $DOCKERFILE

build_image()
{
    printf "docker build image ${DOCKERNAME}\n"
    docker build -t ${DOCKERNAME} --network=host --build-arg NEWUSER=$(whoami) --build-arg NEWUID=$(id -u) $DOCKERFILE || exit 1
}

docker_run()
{
    printf "docker run ${CONTAINER}\n"
    docker run -it --user $(whoami) \
        -v /etc/ssl/certs:/etc/ssl/certs:ro \
        --mount type=bind,source="${SRC_PATH}",target=/clive \
        --name "${CONTAINER}" ${DOCKERNAME} /bin/bash
}

[[ -z $(docker images -q --filter reference=$DOCKERNAME) ]] && build_image
[[ $(docker ps -aq --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || { docker_run ; exit ; } 
[[ $(docker ps --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || docker start ${CONTAINER}

docker attach ${CONTAINER}
