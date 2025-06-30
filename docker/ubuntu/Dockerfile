FROM ubuntu:plucky

RUN apt-get update && \
    apt-get install -y \
            sudo \
            which \
            wget \
            ca-certificates \
            python3 \
            python3-pip \
            git \
            g++ \
            make \
            cmake \
            clang \
            meson \
            libudev-dev \
            libssl-dev \
            liburing-dev \
            libreadline-dev \
            zlib1g-dev \
            xz-utils \
            zip \
            linux-headers-$(uname -r) 

ARG NEWUSER=test
RUN usermod -l $NEWUSER ubuntu && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${NEWUSER} && \
    chmod 0440 /etc/sudoers.d/${NEWUSER}

RUN pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org" && \
    python3 -m pip install --upgrade pip
