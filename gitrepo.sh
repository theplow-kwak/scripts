#!/bin/bash
# https://bytexd.com/how-to-setup-a-private-git-server-on-ubuntu/

if [[ $1 ]]; then
    Repository=$1
    if [[ -e $Repository ]]; then
        echo "Repository $Repository aleady exists!!"
        exit 1
    fi

    if (sudo mkdir /home/git/${Repository}.git); then
        pushd /home/git/${Repository}.git && sudo git init --bare && popd && sudo chown -R git.git /home/git/${Repository}.git
    fi
else
    echo "Usage: $0 Repository"
fi
