#!/bin/bash

while true
do
    if [ -f /shared_keys/validator-${1}.pub ]
    then
        cp /shared_keys/validator-${1}.priv /etc/sawtooth/keys/validator.priv
        cp /shared_keys/validator-${1}.pub /etc/sawtooth/keys/validator.pub

        python3 /root/create_network_keys.py
    fi;

    if [ -f /etc/sawtooth/keys/validator.pub ]
    then
        break;
    fi;

    sleep 0.5;
done;

echo "\n\n #### VALIDATOR ${1} STARTING ####\n\n"
peers=""
last=${@: -1}

for var in "${@:2}"
do
  peers+="tcp://validator-$var:8800"
  if [ "$var" != "$last" ]
  then
    peers+=","
  else
    peers+=''
  fi
done
echo $peers

sawtooth-validator -vv \
    --endpoint tcp://validator-${1}:8800 \
    --bind component:tcp://eth0:4004 \
    --bind network:tcp://eth0:8800 \
    --bind consensus:tcp://eth0:5050 \
    --peering static \
    --peers $peers \
    --scheduler parallel \
    --opentsdb-url http://influxdb:8086 \
    --opentsdb-db metrics