# SHELL := /bin/bash

protobuf:
	python3 -m grpc_tools.protoc -I=consensus/protos --python_out=consensus/pkg/consensus --grpc_python_out=consensus/pkg/consensus consensus/protos/*.proto 

# run:
# 	docker compose down -v && docker compose up --build

SHELL:=/bin/bash

build: prepare
	docker build -t lillepus/sintef-ddpoa-engine:latest .
# This setup minikube so that the image we build using docker
# will be registered there
prepare: 
	eval $(minikube -p minikube docker-env)
clean: 
	minikube kubectl -- delete -f ${PWD}/kubernetes.yml
run: build 
	minikube kubectl -- apply -f ${PWD}/kubernetes.yml

run-from-scratch: clean build run

create-keys: 
	minikube kubectl -- apply -f ${PWD}/create-keys.yml
apply-config-map: 
	minikube kubectl -- apply -f ${PWD}/configmap.yml
remove-config-map: 
	minikube kubectl -- remove -f ${PWD}/configmap.yml