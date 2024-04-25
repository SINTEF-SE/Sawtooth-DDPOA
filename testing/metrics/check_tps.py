import json, os
import numpy

import datetime

def calculate_tps_from_json(fn):
    with open(fn) as f:
        data = json.load(f)

    tps = 0
    # time_diff = data['series'][0]['values'][-1][0] - data['series'][0]['values'][0][0]
    #print(time_diff)
    test_start = data['series'][0]['values'][0][0]
    test_end = data['series'][0]['values'][-1][0]
    print(test_start,test_end)
    # convert date to seconds

    test_start = datetime.datetime.strptime(test_start, '%Y-%m-%dT%H:%M:%SZ')

    test_end = datetime.datetime.strptime(test_end, '%Y-%m-%dT%H:%M:%SZ')

    time_diff = (test_end - test_start).total_seconds()

    for value in data['series'][0]['values']:
        # print(value[0],value[1])
        tps += value[1]

    #averaged tps of all nodes

    return (tps/ len(data['series'][0]['values'])) / time_diff

def calculate_tps_from_dir(dir):
    for fn in os.listdir(dir):
        if fn.endswith("committed_transactions_count.json"):
            return calculate_tps_from_json(f'{dir}/{fn}')

    # return averaged_tps


def find_average_tps_per_rate(tps):
    dict_nodelay = {"pbft" : {}, "ddpoa": {}, "poet": {}}
    dict_delay= {"pbft" : {}, "ddpoa": {}, "poet": {}}
    
    for engine in dict_nodelay:
        for filename in tps:
            print(filename.split('_'))
            delay, nodes,_,slots,engine,rate,run = filename.split('_')
            nodes = int(nodes.split('=')[1])
            match int(delay):
                case 0:
                    dict = dict_nodelay
                case 1:
                    dict = dict_delay

            if nodes not in dict[engine]:
                dict[engine][nodes] = {}

            if rate not in dict[engine][nodes]:
                dict[engine][nodes][rate] = []
            print(engine,rate,run)
            
            if tps[filename] is not None:
                dict[engine][nodes][rate].append(tps[filename])
            
            
    # print(sum_dict(dict_nodelay),)
    return sum_dict(dict_nodelay), sum_dict(dict_delay)

def sum_dict(dict):
    for engine in dict:
        for node in dict[engine]:
            for rate in dict[engine][node]:
                print(engine,node,rate,dict[engine][node][rate])
                if len(dict[engine][node][rate]) > 0:
                    dict[engine][node][rate] = round(sum(dict[engine][node][rate]) / len(dict[engine][node][rate]),3)
    return dict

import csv
def write_to_csv(data,engine,test_fn="latency_test_tp"):
    engines = [*data]

    with open(f"results/{test_fn}.csv", "a") as f:
        writer = csv.writer(f)

        if os.stat(f"results/{test_fn}.csv").st_size == 0:
            writer.writerow(['engine','node', 'rate', 'average_tps'])

        for key in engines:
            nodes = [*data[key]]
            for node in nodes:
                rate = [*data[key][node]]
                block_num = data[key][node].values()


                l = zip(*[[key]*len(rate),[node]*len(rate),rate,block_num])
                writer.writerows(l)

if __name__ == "__main__":

    tps = {}
    for fn in os.listdir('runs'):
        tps[fn] = calculate_tps_from_dir(f'runs/{fn}')
    
    
    average_tps_nodelay, average_tps_delay =   find_average_tps_per_rate(tps) 

    write_to_csv(average_tps_nodelay,"lol",test_fn="latency_test_tp_nodelay")
    write_to_csv(average_tps_delay,"lol",test_fn="latency_test_tp_delay")
