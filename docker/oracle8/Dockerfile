FROM oraclelinux:8

RUN yum install -y \
            wget \
            gcc-toolset-13 \
            clang \
            openssl-devel \
            zlib-devel \
            sqlite-devel \
            readline-devel \
            xz \
            which \
            perl \
            python3 \
            python3-pip \
            cmake \
            git \
            sudo

ENTRYPOINT [ "scl", "enable", "gcc-toolset-13" ]
CMD [ "/bin/bash" ]

ARG NEWUSER=test
ARG NEWUID=1000
RUN adduser --uid $NEWUID --comment "${NEWUSER}" ${NEWUSER} && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$NEWUSER && chmod 0440 /etc/sudoers.d/$NEWUSER

