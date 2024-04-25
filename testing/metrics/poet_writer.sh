#!/bin/bash



# sed {NODE} from template input and output to eof

# sed {PEERS_LIST} from python script

for i in {1..16}
do
    PEERS_LIST=$(python3 create_poet_peers.py $i)

    sed -e "s/{NODE}/$i/g" template.yml  >> poet_writer.yml
    sed -i '' "s/{PEERS_LIST}/$PEERS_LIST/g" poet_writer.yml 

done