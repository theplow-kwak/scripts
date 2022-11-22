#!/bin/bash

rm_container()
{
    _CONTAINER=$1
    if [[ $(docker ps -aq --filter "name=^/$_CONTAINER$" --format '{{.Names}}') == $_CONTAINER ]]; then
        printf "remove container ${_CONTAINER}\n"
        docker rm $_CONTAINER
    fi
}

rm_image()
{
    _DOCKERNAME=$1
    printf "remove docker image ${_DOCKERNAME}\n"
    # _containers=$(docker ps -aq --filter "ancestor=${_DOCKERNAME}" --format '{{.Names}}')
    # for _container in $_containers; do
    #     rm_container ${_container}
    # done
    docker rm -f $(docker ps -aq --filter "ancestor=${_DOCKERNAME}" --format '{{.Names}}')
    docker image rm $_DOCKERNAME
}

build_image()
{
    printf "docker build image ${DOCKERNAME}\n"
    docker build -t ${DOCKERNAME} --network=host --build-arg NEWUSER=$(whoami) --build-arg NEWUID=$(id -u) $DOCKERPATH || exit 1
}

docker_run()
{
    printf "docker run ${CONTAINER}\n"
    docker_cmd=(
        docker run -it --user $(whoami) 
        -v /etc/ssl/certs:/etc/ssl/certs:ro)
    [[ -n $SHAREFOLDER ]] && docker_cmd+=(--mount type=bind,source="${SHAREFOLDER}",target=/host)
    docker_cmd+=(
        --name "${CONTAINER}" ${DOCKERNAME} /bin/bash)

    echo "${docker_cmd[*]}"
    ("${docker_cmd[@]}")
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] dockerimage

Options:
 -d, --docker       Path to the docker file
 -s, --share        Path to the shared folder
 -c, --container    Name of the container what you want to run
 -r, --rm           Remove the container
 -R, --rmi          Remove the docker image and associated containers.

EOM
}

options=$(getopt -n ${0##*/} -o s:d:c:rR \
                --long help,docker:,container:,share,rm,rmi -- "$@")
[ $? -eq 0 ] || { usage; exit 1; }
eval set -- "$options"

while true; do
    case $1 in
        -d | --docker )     DOCKERPATH=${2} ;       shift ;;
        -s | --share )      SHAREFOLDER=${2} ;      shift ;;
        -c | --container )  CONTAINER=${2} ;        shift ;;
        -r | --rm )         removecnt=1 ;;
        -R | --rmi )        removeimg=1 ;;
        -h | --help )       usage ;                 exit ;;
        --)                 shift ;                 break ;;
    esac
    shift
done 

if [[ -n ${DOCKERPATH} ]]; then
    _tmp=$(realpath ${DOCKERPATH})
    DOCKERNAME=${_tmp##*/}
fi

while (($#)); do
    DOCKERNAME=$1
    shift
done

CONTAINER=${CONTAINER:-"${DOCKERNAME}_cnt"}

if [[ -z ${DOCKERNAME} ]] && [[ "${CONTAINER}" == "_cnt" ]]; then
    usage
    docker ps -a
    exit
fi

[[ $removecnt ]] && rm_container ${CONTAINER}
[[ $removeimg ]] && rm_image ${DOCKERNAME}
if [[ $removecnt ]] || [[ $removeimg ]]; then
    exit
fi

[[ -n $DOCKERNAME ]] && [[ -z $(docker images -q --filter reference=$DOCKERNAME) ]] && build_image
[[ $(docker ps -aq --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || { docker_run ; exit ; }
[[ $(docker ps --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || docker start ${CONTAINER}

docker attach ${CONTAINER}
