#!/bin/bash
# https://bytexd.com/how-to-setup-a-private-git-server-on-ubuntu/

git_init_local()
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
        git remote add main git@localhost:/home/git/${Repository}.git
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
    if [[ -e /home/git/${Repository}.git ]]; then
        echo "Repository /home/git/${Repository}.git aleady exists!!"
        return
    fi

    if (sudo -H -u git mkdir /home/git/${Repository}.git); then
        sudo -H -u git git init --bare /home/git/${Repository}.git
    else
        echo "Can't make remode repository"
        exit 1
    fi
}

[[ $1 ]] || { echo "Usage: ${0##*/} Repository"; exit 1; }
git_init_server $1
git_init_local $1
