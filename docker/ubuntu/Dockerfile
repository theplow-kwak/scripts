FROM ubuntu:26.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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
            curl && \
    rm -rf /var/lib/apt/lists/* 

ARG NEWUSER=test
RUN userdel -r ubuntu || true && \
    groupadd -g 1000 $NEWUSER && \
    useradd -r -u 1000 -g 1000 -m -s /bin/bash $NEWUSER && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$NEWUSER && \
    chmod 0440 /etc/sudoers.d/$NEWUSER

RUN pip config set global.trusted-host "pypi.org files.pythonhosted.org pypi.python.org" && \
    python3 -m pip install --upgrade pip --break-system-packages --ignore-installed

USER $NEWUSER
WORKDIR /home/$NEWUSER
