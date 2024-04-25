kubectl delete -f kubernetes_test_file.yml
kubectl delete -f config/influxdb-pv.yaml
kubectl delete -f config/influxdb-pvc.yml
kubectl delete -f config/grafana-provision.yaml

eval $(minikube -p minikube docker-env)
docker build ../ -t ddpoa

python3 compose_writer.py

kubectl apply -f config/influxdb-pv.yaml
kubectl apply -f config/influxdb-pvc.yml
kubectl apply -f config/grafana-provision.yaml

kubectl apply -f kubernetes_test_file.yml

minikube service ddpoa-admin --url