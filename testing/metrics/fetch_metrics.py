
import time
import influxdb
import os
import subprocess

import json
import threading

from kubernetes import client, config, utils
user = 'admin'
password = 'admin'
db = 'metrics'

remote_client = influxdb.InfluxDBClient('localhost','9086', user, password, db)

dirs = os.listdir('runs')

config.load_kube_config()
api = client.ApiClient()

TEST_TIME = 60*10
network_delay = 1

def dump_influx(dir:str):
    if not os.path.exists(f'runs/{dir}'):
        os.makedirs(f'runs/{dir}')

    for item in remote_client.get_list_measurements():
        measurement = str(*item.values())
        resp =remote_client.query(f'select * from metrics.autogen.\"{measurement}\";')

        resp = resp.raw
        with open(f'runs/{dir}/{measurement}.json', 'w') as f:
            json.dump(resp, f)


def create_cluster(nodes=16,rate=12,engine='ddpoa' ):
    subprocess.run(['python3' , 'compose_writer.py', '--nodes', str(nodes), '--rate', str(rate), '--slots', '3','--engine',str(engine)])


def run_kub_file(fn):
    utils.create_from_yaml(k8s_client=api, yaml_file=fn, )

def delete_kub_file(fn):
    subprocess.run(['kubectl', 'delete', '-f', fn])

def run_kub_file_non_client(fn):
    subprocess.run(['kubectl', 'apply', '-f', fn])

def run_test_case(nodes=16,rate=12,slots=3,engine='ddpoa',run=0):
    create_cluster(nodes,rate,engine)
    # get all pods

    if network_delay:
        run_kub_file_non_client("./networkdelay.yml")

    run_kub_file('../config/influxdb-pvc.yml')

    if engine == 'poet':
        run_kub_file('./poet.yml')
    else:
        run_kub_file('./kubernetes_test_file.yml')

    print("##### WAINTING FOR KUB TO STARRTT $$")

    time.sleep(60)

    print("#### RUNNING WORKLOAD#####")
    run_kub_file("./workload_test_file.yml")

    thread = threading.Timer(TEST_TIME, delete_test_case,(nodes,rate,slots,engine,run))

    thread.start()

    thread.join()


def delete_test_case(nodes=16,rate=12,slots=3,engine='ddpoa',run="0"):
    dump_influx(f'{network_delay}_nodes={nodes}_rate={rate}_slots={slots}_{engine}_{run}')

    delete_kub_file("./workload_test_file.yml")

    if engine == 'poet':
        delete_kub_file('./poet.yml')
    else:
        delete_kub_file("./kubernetes_test_file.yml")
    delete_kub_file("../config/influxdb-pvc.yml")
    if network_delay:
        delete_kub_file("./networkdelay.yml")
    print("#### DELETING WORKLOAD #####")

def run_test(num_runs=4,engine="ddpoa",nodes=16,slots=3):

    template = lambda x : [{"nodes":nodes,"rate":x,"slots":slots,"engine":engine,"run":f"{x}_{i}"} for i in range(1,num_runs)]

    for i in range(2,44,4):
        for item in template(i):
            run_test_case(**item)


    
if __name__ == "__main__":
    
    #INCREASE NUMBER OF NODES 
    for number_nodes in range(6,33,4):

        slots = 7 if number_nodes > 16 else 3
        network_delay = 1
        run_test(nodes=number_nodes,slots=slots) #ddpoa test case
        run_test(nodes=number_nodes, engine='pbft', slots=slots) #pbft test case

        network_delay = 0
        run_test(nodes=number_nodes,slots=slots) #ddpoa test case
        run_test(nodes=number_nodes, engine='pbft',slots=slots) #pbft test case
