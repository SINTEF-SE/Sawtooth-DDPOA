#!/bin/bash
kubectl get deployments -o custom-columns='NAME:.metadata.name' | grep -v admin | grep -v NAME | xargs kubectl delete deployment
