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
        git remote add $REMOTE git@localhost:/home/git/${Repository}.git
        git fetch $REMOTE
    fi
    branch=($(git branch --remote --list))
    branchs=(${branch//// })
    echo ${branchs[@]}
    if [[ -n ${branchs[1]} ]] ; then
        git reset --mixed $REMOTE/master --no-refresh
        git branch --set-upstream-to=$REMOTE/master master
    fi
    popd
}

git_init_local2()
{
    Repository=$1
    [[ -e ${Repository} ]] || { echo "Local repository ${Repository} does not exist"; exit 1; }

    pushd ${Repository}
    if [[ ! -e .git ]]; then
        git init
        git config user.email $USER
        git config user.name $USER
        git add *
        git commit -m "Initial Commit"
    fi
    if [[ -z $(git remote) ]] ; then
        git remote add $REMOTE git@localhost:/home/git/${Repository}.git
    fi
    branch=($(git branch --remote --list))
    branchs=(${branch//// })
    echo ${branchs[@]}
    git push --set-upstream ${branchs[0]} ${branchs[1]}
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

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] Repository

Options:
 -s, --sever    Initialize remote repository
 -l, --local    Initialize local repository
 -r, --remote   Set remote name
 -h, --help     Display usage

EOM
}

REMOTE=origin

options=$(getopt -n ${0##*/} -o hslr: \
                --long help,server,local,remote: -- "$@")
[ $? -eq 0 ] || { usage; exit 1; }
eval set -- "$options"

while true; do
    case $1 in
        -s | --server )     _init_sever="yes" ;;
        -l | --local )      _init_local="yes" ;;
        -r | --remote )     REMOTE=$2;  shift ;;
        -h | --help )       usage ;     exit  ;;
        --)                 shift ;     break ;;
    esac
    shift
done 

[[ $1 ]] || { usage; exit; }
[[ $_init_sever == "yes" ]] && git_init_server $1
[[ $_init_local == "yes" ]] && git_init_local $1
