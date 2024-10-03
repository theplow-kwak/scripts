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
    [[ -z ${REPOSITORY} ]] && REPOSITORY=$(docker ps -a --filter "name=^/$CONTAINER$" --format '{{.Image}}')
    docker history --human --format "{{.CreatedBy}}: {{.Size}}" ${REPOSITORY}
    exit
}

function docker_inspect()
{
    docker inspect --format 'User:       {{.Config.User}}' ${CONTAINER}
    docker inspect --format 'Args:       {{.Path}} {{join .Args " "}}' ${CONTAINER}   
    docker inspect --format 'WorkingDir: {{.Config.WorkingDir}}' ${CONTAINER}
    echo "Mounts:"
    docker inspect --format '{{range .Mounts}}{{println " " .Source "\t->" .Destination}}{{end}}' ${CONTAINER}
    exit
}

function docker_import()
{
    [[ -f $DOCKERFILE ]] || exit
    [[ -z $EXT_CMD ]] && docker_cmd=(docker import $DOCKERFILE ${REPOSITORY}) || docker_cmd=(docker import $DOCKERFILE ${REPOSITORY} --change "CMD [${EXT_CMD}]")
    echo "${docker_cmd[@]}"
    ("${docker_cmd[@]}")
    exit
}

function docker_export()
{
    [[ -n $DOCKERFILE ]] || DOCKERFILE=$DOCKERPATH
    docker_cmd=(docker export ${CONTAINER} --output $DOCKERFILE)
    echo "${docker_cmd[@]}"
    ("${docker_cmd[@]}")
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
    _IMAGE=$1
    _CONTAINERS=$(docker ps -a --filter "ancestor=${_IMAGE}" --format '{{.Names}}')
    echo "remove docker image ${_IMAGE} /" $(join , ${_CONTAINERS[@]}) 
    [[ -n $_CONTAINERS ]] && docker rm -f $_CONTAINERS
    docker rmi $_IMAGE
    exit
}

function docker_build()
{
    [[ $FORCE ]] && _force="--no-cache" || _force=""
    [[ $USER_NAME == "root" ]] && USER_NAME=$(whoami)

    docker_cmd=(docker build $_force -t ${REPOSITORY} --network=host --build-arg NEWUSER=$USER_NAME --build-arg NEWUID=$(id -u $USER_NAME) "$DOCKERPATH")
    [[ -n $DOCKERFILE ]] && docker_cmd+=(-f "$DOCKERFILE")
    echo "${docker_cmd[*]}"
    ("${docker_cmd[@]}") || exit 1
}

function docker_run()
{
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

    [[ -z $EXT_CMD ]] && EXT_CMD=/bin/bash || EXT_CMD=(${EXT_CMD//,/ })

    docker_cmd+=(
        --name "${CONTAINER}" ${REPOSITORY} "${EXT_CMD[@]}")

    echo "${docker_cmd[@]}"
    ("${docker_cmd[@]}")
}

function usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] name

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
                    --long help,uname:,docker:,share:,container:,rm,rmi,force,cert,history,inspect,import,export,cmd: -- "$@")
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
                --cert )        share_cert=1 ;;
                --history )     do_history=1 ;;
                --inspect )     do_inspect=1 ;;
                --import )      do_import=1 ;;
                --export )      do_export=1 ;;
                --cmd )         EXT_CMD=$2 ;                shift ;;
            -h | --help )       usage ;                     exit ;;
            --)                 shift ;                     break ;;
        esac
        shift
    done 

    [[ -z $USER_NAME ]] && USER_NAME=$(whoami)
    [[ $USER_NAME == "root" ]] && HOME_FOLDER="/$USER_NAME" || HOME_FOLDER="/home/$USER_NAME" 

    while (($#)); do
        PARAM_NAME=$1
        shift
    done

    if [[ -n ${DOCKERPATH} ]]; then
        DOCKERPATH=$(realpath "${DOCKERPATH}")
        if [[ -f $DOCKERPATH ]]; then
            DOCKERFILE=${DOCKERPATH}
            DOCKERPATH=${DOCKERPATH%/*}
        fi
        REPOSITORY=${PARAM_NAME:-${DOCKERPATH##*/}}
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
}

IMAGES=($(docker images --format '{{.Repository}}'))
CONTAINERS=($(docker ps -a --format '{{.Names}}'))
echo "IMAGES: ${IMAGES[@]}"
echo "CONTAINERS: ${CONTAINERS[@]}"

declare -A SHARES
set_args $@

[[ $(echo ${IMAGES[@]} | grep -ow "$PARAM_NAME") ]] && REPOSITORY=$PARAM_NAME
[[ $(echo ${CONTAINERS[@]} | grep -ow "$PARAM_NAME") ]] && CONTAINER=${CONTAINER:-$PARAM_NAME}
CONTAINER=${CONTAINER:-$REPOSITORY}
printf "Repository: ${REPOSITORY} \n"
printf "Container : ${CONTAINER} \n\n"

if [[ -z ${REPOSITORY} ]] && [[ -z ${CONTAINER} ]]; then
    usage
    docker images
    echo ""
    docker ps -a
    exit
fi

[[ $removecnt ]] && rm_container ${CONTAINER}
[[ $removeimg ]] && rm_image ${REPOSITORY}
[[ $do_history ]] && docker_history
[[ $do_inspect ]] && docker_inspect
[[ $do_import ]] && docker_import
[[ $do_export ]] && docker_export

[[ -n $REPOSITORY ]] && [[ -z $(docker images -q --filter reference=$REPOSITORY) ]] && { docker_build ; docker images ; exit ;}
[[ $(docker ps -a --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || { docker_run ; exit ; }
[[ $(docker ps --filter "name=^/$CONTAINER$" --format '{{.Names}}') == $CONTAINER ]] || docker start ${CONTAINER}

docker attach ${CONTAINER}
