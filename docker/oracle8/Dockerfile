FROM oraclelinux:8

RUN yum install -y \
        ca-certificates \
        gcc-toolset-10 \
        sudo 

ARG NEWUSER=test
ARG NEWUID=1000
RUN adduser --uid $NEWUID --comment "${NEWUSER}" ${NEWUSER} && \
    echo "$NEWUSER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$NEWUSER && chmod 0440 /etc/sudoers.d/$NEWUSER

ENTRYPOINT [ "scl", "enable", "gcc-toolset-10" ]
CMD [ "/bin/bash" ]