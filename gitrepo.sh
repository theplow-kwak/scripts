#!/bin/bash
# https://bytexd.com/how-to-setup-a-private-git-server-on-ubuntu/

git_init_local()
{
    Repository=$1
    [[ -e ${Repository} ]] || { echo "Local repository ${Repository} does not exist"; exit 1; }

    pushd ${Repository}
    if [[ ! -e .git ]]; then
        git init
    fi
    if [[ -z $(git remote) ]] ; then
        git remote add $REPO_NAME git@localhost:/home/git/${Repository}.git
        git fetch $REPO_NAME
    fi
    branch=($(git branch --remote --list))
    branchs=(${branch//// })
    echo ${branchs[@]}
    if [[ -n ${branchs[1]} ]] ; then
        git reset --mixed $REPO_NAME/master --no-refresh
        git branch --set-upstream-to=$REPO_NAME/master master
    fi
    popd
}

git_init_server()
{
    Repository=$1
    [[ $(sudo -H -u git ls /home/git/${Repository}.git 2> /dev/null) ]] && { echo "Repository /home/git/${Repository}.git aleady exists!!"; return; }

    if (sudo -H -u git mkdir /home/git/${Repository}.git); then
        sudo -H -u git git init --bare /home/git/${Repository}.git
    else
        echo "Can't make remode repository"
        exit 1
    fi
}

git_add_remote()
{
    Repository=$1
    if [[ ! -e .git ]]; then
        echo "fatal: not a git repository (or any of the parent directories): .git"
        exit 1
    fi
    if [[ -z $(git remote) ]] ; then
        git remote add $REPO_NAME ${Repository}
        git fetch $REPO_NAME
    fi
    branch=($(git branch --remote --list))
    branchs=(${branch//// })
    echo ${branchs[@]}
    if [[ -n ${branchs[1]} ]] ; then
        git reset --mixed $REPO_NAME/master --no-refresh
        git branch --set-upstream-to=$REPO_NAME/master master
    fi
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] Repository

Options:
 -s, --sever    Initialize remote repository
 -l, --local    Initialize local repository
 -r, --remote   Set remote repository
 -n, --name     Set remote name
 -h, --help     Display usage

EOM
}

REPO_NAME=origin

options=$(getopt -n ${0##*/} -o hslrn: \
                --long help,server,local,remote:,name: -- "$@")
[ $? -eq 0 ] || { usage; exit 1; }
eval set -- "$options"

while true; do
    case $1 in
        -s | --server )     _init_sever="yes" ;;
        -l | --local )      _init_local="yes" ;;
        -n | --name )       REPO_NAME=$2;  shift ;;
        -r | --remote )     REMOTE=$2;  shift ;;
        -h | --help )       usage ;     exit  ;;
        --)                 shift ;     break ;;
    esac
    shift
done 

[[ $1 ]] || { usage; exit; }
[[ $_init_sever == "yes" ]] && git_init_server $1
[[ $_init_local == "yes" ]] && git_init_local $1
