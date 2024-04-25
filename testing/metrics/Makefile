SHELL:=/bin/bash

build: 
	pip3 install -r requirements.txt
prepare: 
	clean
run: # run test and collect metrics to csv
	python3 fetch_metrics.py
	# python3 check_tps.py 
	# python3 metrics_to_csv.py

clean: 
	kubectl delete -f kubernetes_test_file.yml; 
	kubectl delete -f workload_test_file.yml;
	kubectl delete -f ../config/influxdb-pvc.yml;
	kubectl delete -f networkdelay.yml;

create-volume: 
	kubectl apply -f ../config/influxdb-pv.yml

clean-metrics: 
	rm -rf runs/*