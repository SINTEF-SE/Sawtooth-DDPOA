#!/bin/bash

if [ -z "$ISOLATION_ID" ]; then export ISOLATION_ID=latest; fi
if [ -z "$TEST_ID" ]; then export TEST_ID=latest; fi

set -eux

# Clean up docker on exit, even if it failed
function cleanup {
    echo "Done testing"
    # echo "Dumping logs"
    # echo "-- Workload --"
    # docker-compose -p ${ISOLATION_ID} -f fault_tolerance/workload.yml logs
    # echo "-- Alpha --"
    # docker-compose -p ${ISOLATION_ID}-alpha -f fault_tolerance/node.yml logs
    # echo "-- Beta --"
    # docker-compose -p ${ISOLATION_ID}-beta -f fault_tolerance/node.yml logs
    # echo "-- Gamma --"
    # docker-compose -p ${ISOLATION_ID}-gamma -f fault_tolerance/node.yml logs
    # echo "-- Delta --"
    # docker-compose -p ${ISOLATION_ID}-delta -f fault_tolerance/node.yml logs
    # echo "-- Epsilon --"
    # GENESIS=1 docker-compose -p ${ISOLATION_ID}-epsilon -f fault_tolerance/node.yml logs
    # echo "-- Admin --"
    # docker-compose -p ${ISOLATION_ID} -f fault_tolerance/admin.yml logs
    # echo "Shutting down all containers"
    # docker-compose -p ${ISOLATION_ID} -f fault_tolerance/workload.yml down --remove-orphans --volumes
    # docker-compose -p ${ISOLATION_ID}-alpha -f fault_tolerance/node.yml down --remove-orphans --volumes
    # docker-compose -p ${ISOLATION_ID}-beta -f fault_tolerance/node.yml down --remove-orphans --volumes
    # docker-compose -p ${ISOLATION_ID}-gamma -f fault_tolerance/node.yml down --remove-orphans --volumes
    # docker-compose -p ${ISOLATION_ID}-delta -f fault_tolerance/node.yml down --remove-orphans --volumes
    # GENESIS=1 docker-compose -p ${ISOLATION_ID}-epsilon -f fault_tolerance/node.yml down --remove-orphans --volumes
    # docker-compose -p ${ISOLATION_ID} -f fault_tolerance/admin.yml down --remove-orphans --volumes
}

trap cleanup EXIT SIGTERM

echo "Building sawtooth services"
docker-compose -p ${ISOLATION_ID} -f sawtooth-services.yml build

echo "Building testing engine"
# Try to create these if they don't exist
docker network create test_validators_${ISOLATION_ID} || true
docker network create test_rest_apis_${ISOLATION_ID} || true
docker volume create --name=test_shared_data_${ISOLATION_ID} || true

echo "Starting initial network"
docker-compose -p ${ISOLATION_ID} -f fault_tolerance/admin.yml up -d --build --force-recreate
docker-compose -p ${ISOLATION_ID}-alpha -f fault_tolerance/node.yml up -d --build --force-recreate
docker-compose -p ${ISOLATION_ID}-beta -f fault_tolerance/node.yml up -d --build --force-recreate
docker-compose -p ${ISOLATION_ID}-gamma -f fault_tolerance/node.yml up -d --build --force-recreate
docker-compose -p ${ISOLATION_ID}-delta -f fault_tolerance/node.yml up -d --build --force-recreate
GENESIS=1 docker-compose -p ${ISOLATION_ID}-epsilon -f fault_tolerance/node.yml up -d --build --force-recreate

ADMIN=${ISOLATION_ID}_admin_1

echo "Gathering list of initial keys and REST APIs"
INIT_KEYS=($(docker exec ${ADMIN} bash -c '\
  cd /shared_data/validators && paste $(ls -1) -d , | sed s/,/\ /g'))
echo "Initial keys:" ${INIT_KEYS[*]}
INIT_APIS=($(docker exec ${ADMIN} bash -c 'cd /shared_data/rest_apis && ls -d *'))
echo "Initial APIs:" ${INIT_APIS[*]}

echo "Waiting until network has started"
docker exec -e API=${INIT_APIS[0]} ${ADMIN} bash -c 'while true; do \
  BLOCK_LIST=$(sawtooth block list --url "http://$API:8008" 2>&1); \
  if [[ $BLOCK_LIST == *"BLOCK_ID"* ]]; then \
    echo "Network ready" && break; \
  else \
    echo "Still waiting..." && sleep 0.5; \
  fi; done;'

echo "Sleeping 5 seconds before starting workload"
sleep 6
RATE=2 docker-compose -p ${ISOLATION_ID} -f fault_tolerance/workload.yml up -d

echo "Waiting for all nodes to reach block 3"
docker exec ${ADMIN} bash -c '\
  APIS=$(cd /shared_data/rest_apis && ls -d *); \
  NODES_ON_3=0; \
  until [ "$NODES_ON_3" -eq 5 ]; do \
    NODES_ON_3=0; \
    sleep 4.2; \
    for api in $APIS; do \
      BLOCK_LIST=$(sawtooth block list --url "http://$api:8008" \
        | cut -f 1 -d " "); \
      echo $api && echo $BLOCK_LIST;
      if [[ $BLOCK_LIST == *"3"* ]]; then \
        echo "API $api is on block 3" && ((NODES_ON_3++)); \
      else \
        echo "API $api is not yet on block 3"; \
      fi; \
    done; \
  done;'
echo "All nodes have reached block 3!"

echo "Shutting down alpha node"
docker-compose -p ${ISOLATION_ID}-alpha -f fault_tolerance/node.yml stop

echo "Waiting for remaining nodes to reach block 6"
docker exec ${ADMIN} bash -c '\
  APIS=$(cd /shared_data/rest_apis && ls -d *); \
  NODES_ON_6=0; \
  until [ "$NODES_ON_6" -gt 3 ]; do \
    NODES_ON_6=0; \
    sleep 4.2; \
    for api in $APIS; do \
      BLOCK_LIST=$(sawtooth block list --url "http://$api:8008" 2> /dev/null \
        | cut -f 1 -d " "); \
      echo $api && echo $BLOCK_LIST;
      if [[ $BLOCK_LIST == *"6"* ]]; then \
        echo "API $api is on block 6" && ((NODES_ON_6++)); \
      else \
        echo "API $api is not yet on block 6"; \
      fi; \
    done; \
  done;'
echo "Enough nodes have reached block 6!"

echo "Restarting alpha node"
docker-compose -p ${ISOLATION_ID}-alpha -f fault_tolerance/node.yml start

echo "Waiting for all nodes to reach block 20"
docker exec ${ADMIN} bash -c '\
  APIS=$(cd /shared_data/rest_apis && ls -d *); \
  NODES_ON_20=0; \
  until [ "$NODES_ON_20" -eq 5 ]; do \
    NODES_ON_20=0; \
    sleep 4.2; \
    for api in $APIS; do \
      BLOCK_LIST=$(sawtooth block list --url "http://$api:8008" \
        | cut -f 1 -d " "); \
      echo $api && echo $BLOCK_LIST;
      if [[ $BLOCK_LIST == *"20"* ]]; then \
        echo "API $api is on block 20" && ((NODES_ON_20++)); \
      else \
        echo "API $api is not yet on block 20"; \
      fi; \
    done; \
  done;'
echo "All nodes have reached block 20!"