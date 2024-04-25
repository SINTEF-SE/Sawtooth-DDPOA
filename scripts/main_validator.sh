if [ ! -f "/etc/sawtooth/keys/validator.priv" ];
then
  echo "Initializing new blockchain"

 python3 /root/create_network_keys.py

  sawadm keygen
  sawadm keygen validator-1
  sawadm keygen validator-2
  sawadm keygen validator-3
  sawadm keygen validator-4
  sawadm keygen validator-5
  v0=`cat /etc/sawtooth/keys/validator.pub`
  v1=`cat /etc/sawtooth/keys/validator-1.pub`
  v2=`cat /etc/sawtooth/keys/validator-2.pub`
  v3=`cat /etc/sawtooth/keys/validator-3.pub`
  v4=`cat /etc/sawtooth/keys/validator-4.pub`
  v5=`cat /etc/sawtooth/keys/validator-5.pub`
  members="['$v0','$v1','$v2','$v3','$v4','$v5']"
  echo $members

  sawset genesis -k /etc/sawtooth/keys/validator.priv -o config-genesis.batch

  sawset proposal create \
    -k /etc/sawtooth/keys/validator.priv \
    sawtooth.consensus.algorithm.name=ddpoa \
    sawtooth.consensus.algorithm.version=0.1 \
    sawtooth.consensus.ddpoa.members=$members \
    sawtooth.consensus.ddpoa.seats=3 \
    sawtooth.gossip.time_to_live=1 \
    sawtooth.validator.max_transactions_per_block=300 \
    -o config.batch

  sawadm genesis \
    config-genesis.batch \
    config.batch

  mv /etc/sawtooth/keys/validator-* /shared_keys
fi

echo "\n\n #### VALIDATOR 0 STARTING ####\n\n"

sawtooth-validator \
  --endpoint tcp://validator-0:8800 \
  --bind component:tcp://eth0:4004 \
  --bind network:tcp://eth0:8800 \
  --bind consensus:tcp://eth0:5050 \
  --peering static \
  --scheduler parallel \
  --opentsdb-url http://influxdb:8086 \
  --opentsdb-db metrics


  # sawtooth.validator.max_transactions_per_block=200 \