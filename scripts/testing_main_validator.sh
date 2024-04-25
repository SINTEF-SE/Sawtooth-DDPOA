if [ ! -f "/etc/sawtooth/keys/validator.priv" ];
then
  echo "Initializing new blockchain"

 python3 /root/create_network_keys.py

  sawadm keygen
  for i in {1..31}
  do
    sawadm keygen validator-"$i"
  done

  members="['$(cat /etc/sawtooth/keys/validator.pub)',"
    for i in {1..31}
  do
   echo "'$(cat /etc/sawtooth/keys/validator-"$i".pub)'"
   members+="'$(cat /etc/sawtooth/keys/validator-"$i".pub)'"
   if [ "$i" != 32 ]
   then
     members+=","
   else
     members+="]"
   fi
  done
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