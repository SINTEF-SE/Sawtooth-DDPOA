if [ ! -e "/etc/sawtooth/keys/validator.pub" ]; then sawadm keygen; fi
if [ ! -e "/shared_data/validators/$$(hostname)" ]; then cat "/etc/sawtooth/keys/validator.pub" > "/shared_data/validators/$$(hostname)"; fi
echo "-- /var/lib/sawtooth" && ls "/var/lib/sawtooth" &&  echo "-- /shared_data/validators" && ls "/shared_data/validators" && ls "/shared_data/validators"

if [ ${GENESIS:-0} != 0 -a ! -e /shared_data/genesis.batch ]; then
echo "Running Genesis" && sawset genesis -k /etc/sawtooth/keys/validator.priv sawtooth.consensus.algorithm.name=ddpoa sawtooth.consensus.algorithm.version=1.0 sawtooth.gossip.time_to_live=1 -o config-genesis.batch &&
sawadm genesis config-genesis.batch config.batch && cp /var/lib/sawtooth/genesis.batch /shared_data/genesis.batch && ls /var/lib/sawtooth
fi

export PEERS=$$(for host in $$(ls /shared_data/validators -1); do
  if [ $$host != $$(hostname) ]; then
    echo \\\"tcp://$$host:8800\\\";
  fi; done | tr \\\"\n\\\" \\\",\\\" | sed s\\/,$$\\/\\\n\\/);

echo "-- PEERS " && echo "PEERS=$$PEERS";
if [ "$$PEERS" = "" ]; then
 echo "No peers to connect to...";
 sawtooth-validator -vv --endpoint tcp://$$(hostname):8800 --bind component:tcp://eth0:4004 --bind network:tcp://eth1:8800 --bind consensus:tcp://eth0:5050 --peering static --scheduler parallel; else
   echo "Connecting to $$PEERS";
     sawtooth-validator -vv --endpoint tcp://$$(hostname):8800 --bind component:tcp://eth0:4004 --bind network:tcp://eth1:8800 --bind consensus:tcp://eth0:5050 --peering static --peers $$PEERS --scheduler parallel;
     fi


