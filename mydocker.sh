#!/bin/bash

function join() 
{
    local separator="$1"
    shift
    local first="$1"
    shift
    printf "%s" "$first" "${@/#/$separator}"
}

function docker_history()
{
    docker history --human --format "{{.CreatedBy}}: {{.Size}}" ${DOCKERNAME}
    exit
}

function docker_inspect()
{
    docker inspect --format 'User:       {{.Config.User}}' ${CONTAINER}
    docker inspect --format 'Args:       {{join .Args " "}}' ${CONTAINER}
    docker inspect --format 'WorkingDir: {{.Config.WorkingDir}}' ${CONTAINER}
    echo "Mounts:"
    docker inspect --format '{{range .Mounts}}{{println " " .Source "\t->" .Destination}}{{end}}' ${CONTAINER}
    exit
}

function rm_container()
{
    _CONTAINER=$1
    if [[ $(docker ps -a --filter "name=^/$_CONTAINER$" --format '{{.Names}}') == $_CONTAINER ]]; then
        printf "remove container ${_CONTAINER}\n"
        docker rm $_CONTAINER
    fi
    exit
}

function rm_image()
{
    _DOCKERNAME=$1
    _CONT=$(docker ps -a --filter "ancestor=${_DOCKERNAME}" --format '{{.Names}}')
    echo "remove docker image ${_DOCKERNAME} /" $(join , ${_CONT[@]}) 
    [[ -n $_CONT ]] && docker rm -f $_CONT
    docker rmi $_DOCKERNAME
    exit
}

function docker_build()
{
    printf "docker build image ${DOCKERNAME}\n"
    [[ $FORCE ]] && _force="--no-cache" || _force=""
    [[ $USER_NAME == "root" ]] && USER_NAME=$(whoami)

    docker_cmd=(docker build $_force -t ${DOCKERNAME} --network=host --build-arg NEWUSER=$USER_NAME --build-arg NEWUID=$(id -u $USER_NAME) "$DOCKERPATH")
    [[ -n $DOCKERFILE ]] && docker_cmd+=(-f "$DOCKERFILE")
    echo "${docker_cmd[*]}"
    ("${docker_cmd[@]}") || exit 1
}

function docker_run()
{
    printf "docker run ${CONTAINER}\n"
    docker_cmd=(
        docker run -it --user $USER_NAME
        -v /etc/timezone:/etc/timezone:ro
        -e TZ=Asia/Seoul
        --hostname ${CONTAINER}
        )
    if [[ $share_cert ]]; then
        [[ -d /etc/ssl/certs ]] && docker_cmd+=(-v /etc/ssl/certs:/etc/ssl/certs:ro)
        [[ -d /etc/pki/ca-trust ]] && docker_cmd+=(-v /etc/pki/ca-trust:/etc/pki/ca-trust:ro)
    fi

    for _bind in ${!SHARES[@]}; do
        _path=${SHARES[$_bind]}
        docker_cmd+=(--mount type=bind,source="${_path}",target=$HOME_FOLDER/$_bind)
    done
    docker_cmd+=(--workdir $HOME_FOLDER/$WORKDIR)

    docker_cmd+=(
        --name "${CONTAINER}" ${DOCKERNAME} /bin/bash)

    echo "${docker_cmd[@]}"
    ("${docker_cmd[@]}")
}

function usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] dockerimage

Options:
 -u, --uname <NAME>             The login USER name
 -d, --docker <DOCKER>          Path to the docker file
 -s, --share <SHARE>            Path to the shared folder
 -c, --container <CONTAINER>    Name of the container what you want to run
 -r, --rm                       Remove the container
 -R, --rmi                      Remove the docker image and associated containers.

EOM
}

function set_args()
{
    options=$(getopt -n ${0##*/} -o u:d:s:c:rRf \
                    --long help,uname:,docker:,share:,container:,rm,rmi,force,cert,history,inspect -- "$@")
    [ $? -eq 0 ] || { usage; exit 1; }
    eval set -- "$options"

    while true; do
        case $1 in
            -u | --uname )      USER_NAME=$2 ;              shift ;;    # set login user name
            -d | --docker )     DOCKERPATH=$2 ;             shift ;;
            -s | --share )      SHAREFOLDERS+=(${2//,/ }) ; shift ;;
            -c | --container )  CONTAINER=$2 ;              shift ;;
            -f | --force )      FORCE=1 ;;
            -r | --rm )         removecnt=1 ;;
            -R | --rmi )        removeimg=1 ;;
                --cert )       share_cert=1 ;;
                --history )    do_history=1 ;;
                --inspect )    do_inspect=1 ;;
            -h | --help )       usage ;                     exit ;;
            --)                 shift ;                     break ;;
        esac
        shift
    done 

    [[ -z $USER_NAME ]] && USER_NAME=$(whoami)
    [[ $USER_NAME == "root" ]] && HOME_FOLDER="/$USER_NAME" || HOME_FOLDER="/home/$USER_NAME" 

    if [[ -n ${DOCKERPATH} ]]; then
        DOCKERPATH=$(realpath "${DOCKERPATH}")
        if [[ -f $DOCKERPATH ]]; then
            DOCKERFILE=${DOCKERPATH}
            DOCKERPATH=${DOCKERPATH%/*}
        fi
        DOCKERNAME=${DOCKERPATH##*/}
        printf "Docker path: $DOCKERPATH\n"
        printf "Docker file: $DOCKERFILE\n"
    fi

    for SHAREFOLDER in ${SHAREFOLDERS[@]};
    do
        IFS=":" read -ra _split <<< "$SHAREFOLDER"
        _tmp=$(realpath "${_split[0]}")
        _path=${_tmp%/}
        _bind=${_split[1]}
        [[ -z $_bind ]] && _bind=${_path##*/}
        printf "bind ${_path} to $_bind\n"
        
        SHARES[${_bind}]=$_path
        WORKDIR=${WORKDIR:-$_bind}
    done

    while (($#)); do
        DOCKERNAME=$1
        shift
    done
}

declare -A SHARES
set_args $@

CONTAINER=${CONTAINER:-"${DOCKERNAME}_cnt"}
printf "ImageName: ${DOCKERNAME} \n"
printf "Container: ${CONTAINER} \n\n"

if [[ -z ${DOCKERNAME} ]] && [[ "${CONTAINER}" == "_cnt" ]]; then
    usage
    docker images
    echo ""
    docker ps -a
    exit
fi

[[ $removecnt ]] && rm_container ${CONTAINER}
[[ $removeimg ]] && rm_image ${DOCKERNAME}
[[ $do_history ]] && docker_history ${DOCKERNAME}
[[ $do_inspect ]] && docker_inspect ${DOCKERNAME}

[[ -n $DOCKERNAME ]] && [[ -z $(docker images -q --filter reference=$DOCKERNAME) ]] && { docker_build ; docker images ; exit ;}
[[ $(docker ps -a --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || { docker_run ; exit ; }
[[ $(docker ps --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || docker start ${CONTAINER}

docker attach ${CONTAINER}
