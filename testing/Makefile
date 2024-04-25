SHELL:=/bin/bash

build: prepare
	docker build -t lillepus/sintef-ddpoa-engine:latest .
# This setup minikube so that the image we build using docker
# will be registered there
prepare: 
	eval $(minikube -p minikube docker-env)
clean: 
	kubectl delete -f ${PWD}/kubernetes_test_file.yml
run: build 
	kubectl apply -f ${PWD}/kubernetes_test_file.yml

run-from-scratch: clean build run

create-keys: 
	kubectl apply -f ${PWD}/create-keys.yml
apply-config-map: 
	kubectl apply -f ${PWD}/configmap.yml
remove-config-map: 
	kubectl remove -f ${PWD}/configmap.yml