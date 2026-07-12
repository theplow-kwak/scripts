FROM ubuntu:26.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
            sudo \
            which \
            wget \
            ca-certificates \
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
            curl \
            iproute2 \
            iputils-ping \
            dnsutils \
            netcat-openbsd \
            traceroute && \
    rm -rf /var/lib/apt/lists/* 

ARG NEWUSER=test
RUN userdel -r ubuntu || true && \
    groupadd -g 1000 $NEWUSER && \
    useradd -r -u 1000 -g 1000 -m -s /bin/bash $NEWUSER && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$NEWUSER && \
    chmod 0440 /etc/sudoers.d/$NEWUSER

USER $NEWUSER
WORKDIR /home/$NEWUSER