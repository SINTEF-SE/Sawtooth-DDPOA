FROM ubuntu:22.04

RUN apt-get update

RUN apt-get install -y python3-pip --fix-missing

RUN pip3 install protobuf==3.20.1 sawtooth-sdk requests cbor

ENTRYPOINT ["tail", "-f", "/dev/null"]

COPY . /intkey

WORKDIR /intkey