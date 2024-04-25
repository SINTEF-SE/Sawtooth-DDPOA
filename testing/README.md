
ssh inn i clusteret og lag /mnt/data

```bash
minikube ssh -- sudo mkdir /mnt/data
kubectl apply -f config/influxdb-pv.yaml
kubectl apply -f config/influxdb-pvc.yaml
kubectl apply -f config/grafana-provision.yaml
```