FROM alpine:latest
LABEL maintainer="theplow"

RUN sed -i 's/https/http/' /etc/apk/repositories && \
    apk update && apk upgrade && \
    apk add --no-cache \
    ca-certificates \
    g++ \
    make \
    cmake \
    meson \
    git \
    zip \
    linux-headers \
    musl-dev \
    util-linux-dev \
    zlib-dev \
    zlib-static \
    openssl-dev \
    openssl-libs-static \
    binutils-gold \
    libtool \
    bash \
    sudo

ARG NEWUSER=test
ARG NEWUID=1000
RUN adduser --disabled-password --uid $NEWUID --gecos "${NEWUSER}" ${NEWUSER} && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$NEWUSER && chmod 0440 /etc/sudoers.d/$NEWUSER
