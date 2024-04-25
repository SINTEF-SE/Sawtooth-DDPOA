FROM ubuntu:20.04

RUN apt update

RUN apt install -y --fix-missing curl gnupg python3-pip python3-setuptools

RUN pip3 install requests protobuf==3.20.1 sawtooth-sdk pyzmq STVPoll==0.2.0 grpcio

RUN mkdir -p /var/log/sawtooth

RUN mkdir -p /project/

COPY . /project/

WORKDIR /project/consensus

RUN pip3 install .