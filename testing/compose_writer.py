import random
import yaml
import argparse

parser = argparse.ArgumentParser(description='Kubernetes deployment writer')

parser.add_argument('-r','--rate', default=60,type=int, help='workload rate')
parser.add_argument('-n','--nodes', default=8,type=int, help='number of consensus nodes')
parser.add_argument('-e' ,'--engine', default="ddpoa",type=str, help='engine to use (ddpoa or pbft)')
parser.add_argument('-s' ,'--slots', default=5,type=str, help='number of epoch slots')

args = parser.parse_args()


INDENT_LEVEL = 2
ENABLE_GRAFANA = True

SLOTS = args.slots
WORKLOAD_RATE = args.rate
NUM_CONSENSUS_NODES = args.nodes
print(args)

def write_indent_level(n):
    return " " * (n * INDENT_LEVEL)


def write_list_at_indent_level(n, list):
    retval = ""
    for entry in list:
        retval += write_indent_level(n) + "- " + entry + "\n"
    return retval


def write_inline_list(list):
    return ",".join(list)




class Volumes:
    def __init__(self, keys):
        if keys:
            self.keys = keys
        else:
            self.keys = ""


class Services(object):
    def __init__(self, services=None):
        if services is None:
            services = []
        else:
            self.services = services

    def get_serivces(self):
        return self.services


class ValidatorService(object):
    def __init__(self, hostname, image, volumes, expose, working_dir, entrypoint, stop_signal, depends_on=None):
        self.stop_signal = stop_signal
        self.entrypoint = entrypoint
        self.working_dir = working_dir
        self.expose = expose
        self.volumes = volumes
        self.image = image
        self.hostname = hostname
        self.depends_on = depends_on

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.hostname + ":\n"
        retval += write_indent_level(2) + f"hostname: {self.hostname}\n"
        retval += write_indent_level(2) + f"image: {self.image}\n"
        retval += write_indent_level(2) + f"volumes:\n" + write_list_at_indent_level(3, self.volumes)
        retval += write_indent_level(2) + f"expose:\n" + write_list_at_indent_level(3, self.expose)
        retval += write_indent_level(2) + f"working_dir: {self.working_dir}\n"
        retval += write_indent_level(2) + f"command: {self.entrypoint}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        if self.depends_on:
            retval += write_indent_level(2) + f"depends_on:\n" + write_list_at_indent_level(3, self.depends_on)
        return retval


class ConsensusService:
    def __init__(self, hostname, build_context, build_dockerfile, command, stop_signal, depends_on):
        self.hostname = hostname
        self.build_context = build_context
        self.build_dockerfile = build_dockerfile
        self.command = command
        self.stop_signal = stop_signal
        self.depends_on = depends_on

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.hostname + ":\n"
        retval += write_indent_level(2) + f"hostname: {self.hostname}\n"
        retval += write_indent_level(2) + "build:\n"
        retval += write_indent_level(3) + f"context: {self.build_context}\n"
        retval += write_indent_level(3) + f"dockerfile: {self.build_dockerfile}\n"
        retval += write_indent_level(2) + f"command: {self.command}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        retval += write_indent_level(2) + f"depends_on:\n" + write_list_at_indent_level(3, self.depends_on)
        return retval


class RestApiService:
    def __init__(self, hostname, image, expose_list, command, stop_signal):
        self.hostname = hostname
        self.image = image
        self.expose_list = expose_list
        self.command = command
        self.stop_signal = stop_signal

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.hostname + ":\n"
        retval += write_indent_level(2) + f"hostname: {self.hostname}\n"
        retval += write_indent_level(2) + f"image: {self.image}\n"
        retval += write_indent_level(2) + f"expose:\n" + write_list_at_indent_level(3, self.expose_list)
        retval += write_indent_level(2) + f"command: {self.command}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        return retval

class SettingsService:
    def __init__(self, hostname, image, command, stop_signal):
        self.hostname = hostname
        self.image = image
        self.command = command
        self.stop_signal = stop_signal

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.hostname + ":\n"
        retval += write_indent_level(2) + f"hostname: {self.hostname}\n"
        retval += write_indent_level(2) + f"image: {self.image}\n"
        retval += write_indent_level(2) + f"command: {self.command}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        return retval


class TransactionProcessorService:
    def __init__(self, hostname, image, command, stop_signal):
        self.hostname = hostname
        self.image = image
        self.command = command
        self.stop_signal = stop_signal

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.hostname + ":\n"
        retval += write_indent_level(2) + f"hostname: {self.hostname}\n"
        retval += write_indent_level(2) + f"image: {self.image}\n"
        retval += write_indent_level(2) + f"expose:\n" + write_list_at_indent_level(3, ["4004"])
        retval += write_indent_level(2) + f"command: {self.command}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        return retval

    def get_as_kubernetes_yaml(self):
        retval = ""
        retval += write_indent_level(5) + "- name: sawtooth-intkey-tp-python\n"
        retval += write_indent_level(6) + f"image: {self.image}\n"
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + '- "intkey-tp-python -vvv -C tcp://$HOSTNAME:4004"'


class TransactionFamilyTester:
    def __init__(self, container_name, build_context, build_dockerfile, stop_signal):
        self.container_name = container_name
        self.build_context = build_context
        self.build_dockerfile = build_dockerfile
        self.stop_signal = stop_signal

    def get_as_yaml_obj(self):
        retval = ""
        retval += write_indent_level(1) + self.container_name + ":\n"
        retval += write_indent_level(2) + f"container_name: {self.container_name}\n"
        retval += write_indent_level(2) + "build:\n"
        retval += write_indent_level(3) + f"context: {self.build_context}\n"
        retval += write_indent_level(3) + f"dockerfile: {self.build_dockerfile}\n"
        retval += write_indent_level(2) + f"stop_signal: {self.stop_signal}\n"
        return retval


def ValidatorConstructor(loader, node):
    fields = loader.construct_mapping(node)
    return ValidatorService(**fields)


def validator_representer(dumper: yaml.SafeDumper, validator: ValidatorService) -> yaml.nodes.MappingNode:
    """Represent an Validator instance as a YAML mapping node."""

    return dumper.represent_mapping(f"{validator.hostname}", {
        "hostname": validator.hostname,
        "image": validator.image,
        "volumes": validator.volumes,
        "expose": validator.expose,
        "working_dir": validator.working_dir,
        "entrypoint": validator.entrypoint,
        "stop_signal": validator.stop_signal
    })


def int_list_to_string_comma_list(lst):
    retval = ""
    for entry in lst:
        retval += f"\"{entry}\", "
    return retval[:len(retval) - 2]


def get_dumper():
    safe_dumper = yaml.SafeDumper
    safe_dumper.add_representer(ValidatorService, validator_representer)
    return safe_dumper


def create_docker_compose_file():
    t_validator = ValidatorService("validator-1", "hyperledger/sawtooth-validator:chime",
                                   ["keys:/shared_keys", "./scripts/main_validator.sh:/root/start.sh",
                                    "./scripts/create_network_keys.py:/root/create_network_keys.py1"],
                                   ["4004", "8800", "5005", "5050"], "/root", ["bash", "start.sh"], "SIGKILL")
    service_list = []
    # service_list.append(t_validator)
    # yaml.add_constructor('- !!python/object:__main__.ValidatorService', ValidatorConstructor)
    #    with open("test_file.yml", "w") as outfile:
    #        yaml.dump(t_validator, outfile, default_flow_style=False)
    peer_list = [peer for peer in range(NUM_CONSENSUS_NODES)]
    all_validators = []
    for i in range(NUM_CONSENSUS_NODES):
        all_validators.append(f"validator-{i}")
    for i in range(NUM_CONSENSUS_NODES):
        current_peer_list = peer_list[:i] + peer_list[i + 1:]
        max_peer_list = random.sample(current_peer_list, 10)
        if i == 0:
            service_list.append(ValidatorService(f"validator-{i}", "hyperledger/sawtooth-validator:chime",
                                                 ["keys:/shared_keys",
                                                  "./scripts/testing_main_validator.sh:/root/start.sh",
                                                  "./scripts/create_network_keys.py:/root/create_network_keys.py"],
                                                 ["4004", "8800", "5005", "5050"], "/root", ["bash", "start.sh"],
                                                 "SIGKILL"))
        else:
            command = ["bash", "start.sh", f"{i}"]
            command.extend([str(peer) for peer in max_peer_list])
            service_list.append(ValidatorService(f"validator-{i}", "hyperledger/sawtooth-validator:chime",
                                                 ["keys:/shared_keys", "./scripts/testing_start.sh:/root/start.sh",
                                                  "./scripts/create_network_keys.py:/root/create_network_keys.py"],
                                                 ["4004", "8800", "5005", "5050"], "/root", command,
                                                 "SIGKILL", [f"validator-{i - 1}"]))
        service_list.append(ConsensusService(f"consensus-{i}", ".", "Dockerfile",
                                             f'"bash -c \\"python3 main.py -vvv --connect tcp://validator-{i}:5050 \\""',
                                             "SIGKILL", all_validators))
        service_list.append(RestApiService(f"rest-api-{i}", "hyperledger/sawtooth-rest-api:chime", ["4004", "8800"],
                                           f"sawtooth-rest-api -v --connect tcp://validator-{i}:4004 --bind rest-api-{i}:8008 --opentsdb-url http://influxdb:8086 --opentsdb-db metrics",
                                           "SIGKILL"))
        service_list.append(SettingsService(f"settings-tp-{i}", "hyperledger/sawtooth-settings-tp:chime",
                                            f"settings-tp -C tcp://validator-{i}:4004", "SIGKILL"))
        service_list.append(TransactionProcessorService(f"intkey-tp-{i}", "hyperledger/sawtooth-intkey-tp-rust:latest",
                                                        f"intkey-tp-rust -C tcp://validator-{i}:4004", "SIGKILL"))
    service_list.append(TransactionFamilyTester("intkey", "./testing/intkey", "Dockerfile", "SIGKILL"))
    services = Services(service_list)
    # I Dont understand pyyaml so I just write my own custom shit since... that will work
    with open("test_file.yml", "w") as outfile:
        outfile.write("version: \"3.6\"\n")
        outfile.write("\n")
        outfile.write("volumes:\n")
        outfile.write("  keys:\n\n")

        outfile.write("services:\n")
        for service in services.get_serivces():
            outfile.write(service.get_as_yaml_obj())
            outfile.write("\n")

        # influx
        influx_params = ["INFLUXDB_ADMIN_ENABLED=true", "INFLUXDB_ADMIN_USER=admin", "INFLUXDB_ADMIN_PASSWORD=admin",
                         "INFLUXDB_DB=metrics", "INFLUXDB_USER=\"\"", "INFLUXDB_USER_PASSWORD=\"\""]
        outfile.write("\tinfluxdb:\n")
        outfile.write("\t\timage: influxdb:1.7-alpine\n")
        outfile.write("\t\tenvironment:\n")
        outfile.write(write_list_at_indent_level(5, influx_params))
        outfile.write("\t\tports:\n")
        outfile.write("\t\t\t- \"8086:8086\"\n")
        outfile.write("\t\tstop_signal: SIGKILL\n")
        outfile.write("\n")

        # grafana
        grafana_ports = ["\"4000:3000\""]
        grafana_depends_on = ["influxdb"]
        outfile.write("\tgrafana:\n")
        outfile.write("\t\timage: grafana/grafana:6.0.0\n")
        outfile.write("\t\tports:\n")
        outfile.write(write_list_at_indent_level(4, grafana_ports))
        outfile.write("\t\tdepends_on:\n")
        outfile.write(write_list_at_indent_level(4, grafana_depends_on))
        outfile.write("\t\tstop_signal: SIGKILL\n")


# 16, ddpoa-test
def create_workload_pod(pod_name,num_nodes):
    retval = "\n"
    retval += "- apiVersion: apps/v1\n"
    retval += write_indent_level(1) + "kind: Deployment\n"
    retval += write_indent_level(1) + "metadata:\n"
    retval += write_indent_level(2) + f"name: {pod_name}-test\n"
    retval += write_indent_level(1) + f"spec:\n"
    retval += write_indent_level(2) + "replicas: 1\n"
    retval += write_indent_level(2) + "selector:\n"
    retval += write_indent_level(3) + "matchLabels:\n"
    retval += write_indent_level(4) + f"name: {pod_name}-test\n"
    retval += write_indent_level(2) + "template:\n"
    retval += write_indent_level(3) + "metadata:\n"
    retval += write_indent_level(4) + f"labels:\n"
    retval += write_indent_level(5) + f"name: {pod_name}-test\n"
    retval += write_indent_level(3) + "spec:\n"
    retval += write_indent_level(4) + "volumes:\n"
    retval += write_indent_level(5) + f"- name: shared\n"
    retval += write_indent_level(6) + "emptyDir: {} \n"
    retval += write_indent_level(4) + "containers:\n"

    retval += write_indent_level(5) + f"- name: {pod_name}-shell\n"
    retval += write_indent_level(6) + "image: lillepus/sawtooth-admin:latest\n"  # TODO: Change me
    retval += write_indent_level(6) + "imagePullPolicy: IfNotPresent\n"
    retval += write_indent_level(6) + "volumeMounts: \n"
    retval += write_indent_level(6) + "- name: shared \n"
    retval += write_indent_level(7) + "mountPath: /shared\n"
    retval += write_indent_level(6) + "command:\n"
    retval += write_indent_level(7) + "- bash\n"
    retval += write_indent_level(6) + "args:\n"
    retval += write_indent_level(7) + "- -c\n"
    retval += write_indent_level(7) + "- |\n"
    retval += write_indent_level(9) + "rm -rf /shared/* && \\\n"
    retval += write_indent_level(9) + "ls /shared && \\\n"
    retval += write_indent_level(9) + "mkdir -p /shared/keys && \\\n"
    retval += write_indent_level(9) + "sawtooth keygen --key-dir /shared/keys workload && \\\n"
    retval += write_indent_level(9) + "while true; do sleep 30; done; \\\n"
    #workload
    retval += write_indent_level(5) + f"- name: {pod_name}-workload\n"
    retval += write_indent_level(6) + "image: hyperledger/sawtooth-intkey-workload:latest\n"  # TODO: Change me
    retval += write_indent_level(6) + "imagePullPolicy: IfNotPresent\n"
    retval += write_indent_level(6) + "volumeMounts: \n"
    retval += write_indent_level(6) + "- name: shared \n"
    retval += write_indent_level(7) + "mountPath: /shared\n"
    retval += write_indent_level(6) + "command:\n"
    retval += write_indent_level(7) + "- bash\n"

    retval += write_indent_level(6) + "args:\n"
    retval += write_indent_level(7) + "- -c\n"
    retval += write_indent_level(7) + "- |\n"

    retval += write_indent_level(9) + "intkey-workload \\\n"
    retval += write_indent_level(9) + "--key-file /shared/keys/workload.priv \\\n"
    retval += write_indent_level(9) + f"--rate {WORKLOAD_RATE} \\\n"
    retval += write_indent_level(9) + "--urls "
    for i in range(num_nodes):
        retval += f"http://$SAWTOOTH_{i}_SERVICE_HOST:8008,"
    retval += write_indent_level(9) + "\\\n"
    return retval

def create_admin_pod(pod_name,num_nodes):
    retval = ""
    retval += "- apiVersion: apps/v1\n"
    retval += write_indent_level(1) + "kind: Deployment\n"
    retval += write_indent_level(1) + "metadata:\n"
    retval += write_indent_level(2) + f"name: {pod_name}-admin\n"
    retval += write_indent_level(1) + f"spec:\n"
    retval += write_indent_level(2) + "replicas: 1\n"
    retval += write_indent_level(2) + "selector:\n"
    retval += write_indent_level(3) + "matchLabels:\n"
    retval += write_indent_level(4) + f"name: {pod_name}-admin\n"
    retval += write_indent_level(2) + "template:\n"
    retval += write_indent_level(3) + "metadata:\n"
    retval += write_indent_level(4) + f"labels:\n"
    retval += write_indent_level(5) + f"name: {pod_name}-admin\n"
    retval += write_indent_level(3) + "spec:\n"
    retval += write_indent_level(4) + "volumes:\n"

    retval += write_indent_level(5) + f"- name: influxdb-store \n"
    retval += write_indent_level(6) + "persistentVolumeClaim: \n"
    retval += write_indent_level(7) + "claimName: influxdb-store \n"
    retval += write_indent_level(5) + f"- configMap:\n"
    retval += write_indent_level(7) + "name: grafana-provision \n"
    retval += write_indent_level(6) + "name: grafana-provision \n"

    retval += write_indent_level(4) + "containers:\n"
    retval += write_indent_level(5) + f"- name: {pod_name}-grafana\n"
    retval += write_indent_level(6) + "image: grafana/grafana:6.0.0\n"
    retval += write_indent_level(6) + "volumeMounts: \n"
    retval += write_indent_level(7) + "- mountPath: /etc/grafana/provisioning/datasources/grafana-provision.yaml \n"
    retval += write_indent_level(8) + "name: grafana-provision\n"
    retval += write_indent_level(8) + "readOnly: True\n"
    retval += write_indent_level(8) + "subPath: grafana-provision.yaml\n"

    retval += write_indent_level(6) + "ports:\n"
    retval += write_indent_level(7) + "- name: grafana\n"
    retval += write_indent_level(8) + "containerPort: 3000\n"




    retval += write_indent_level(5) + f"- name: {pod_name}-influxdb\n"
    retval += write_indent_level(6) + "image: influxdb:1.7-alpine\n"
    retval += write_indent_level(6) + "volumeMounts: \n"
    retval += write_indent_level(7) + "- mountPath: /var/lib/influxdb\n"
    retval += write_indent_level(8) + "name: influxdb-store\n"
    retval += write_indent_level(6) + "ports:\n"
    retval += write_indent_level(7) + "- name: influxdb\n"
    retval += write_indent_level(8) + "containerPort: 8086\n"
    retval += write_indent_level(6) + "env:\n"
    retval += write_indent_level(7) + "- name: INFLUXDB_ADMIN_ENABLED\n"
    retval += write_indent_level(8) + "value: \"true\"\n"
    retval += write_indent_level(7) + "- name: INFLUXDB_ADMIN_USER\n"
    retval += write_indent_level(8) + "value: \"admin\"\n"
    retval += write_indent_level(7) + "- name: INFLUXDB_ADMIN_PASSWORD\n"
    retval += write_indent_level(8) + "value: \"admin\"\n"
    retval += write_indent_level(7) + "- name: INFLUXDB_DB\n"
    retval += write_indent_level(8) + "value: metrics\n"
    retval += write_indent_level(7) + "- name: INFLUXDB_USER\n"
    retval += write_indent_level(8) + "value: \"\" \n"
    retval += write_indent_level(7) + "- name: INFLUXDB_USER_PASSWORD\n"
    retval += write_indent_level(8) + "value: \"\" \n"


    retval += "- apiVersion: v1\n"
    retval += write_indent_level(1) + "kind: Service\n"
    retval += write_indent_level(1) + "metadata:\n"
    retval += write_indent_level(2) + f"name: {pod_name}-admin\n"
    retval += write_indent_level(1) + "spec:\n"
    retval += write_indent_level(2) + "type: NodePort\n"
    retval += write_indent_level(2) + "selector:\n"
    retval += write_indent_level(3) + f"name: {pod_name}-admin\n"
    retval += write_indent_level(2) + "ports:\n"
    retval += write_indent_level(3) + "- name: grafana\n"
    retval += write_indent_level(4) + "protocol: TCP\n"
    retval += write_indent_level(4) + "port: 3000\n"
    retval += write_indent_level(4) + "targetPort: 3000\n"
    retval += write_indent_level(4) + "nodePort: 30000\n"
    retval += write_indent_level(3) + "- name: influxdb\n"
    retval += write_indent_level(4) + "protocol: TCP\n"
    retval += write_indent_level(4) + "port: 8086\n"
    retval += write_indent_level(4) + "targetPort: 8086\n"


    return retval

def create_custom_sawtooth_pod(num_pods, pod_name):
    retval = ""
    for i in range(num_pods):
        engines = {"ddpoa" : {"command":f'sleep {10 if i else 5} && python3 main.py -vvv --connect tcp://$HOSTNAME:5050',"image":"ddpoa:latest","version":"0.1"},
          "pbft" : {"command":"pbft-engine -vv --connect tcp://$HOSTNAME:5050", "image":"hyperledger/sawtooth-pbft-engine:chime","version":"1.0"},
            }

        retval += "- apiVersion: apps/v1\n"
        retval += write_indent_level(1) + "kind: Deployment\n"
        retval += write_indent_level(1) + "metadata:\n"
        retval += write_indent_level(2) + f"name: {pod_name}-{i}\n"
        retval += write_indent_level(1) + f"spec:\n"
        retval += write_indent_level(2) + "replicas: 1\n"
        retval += write_indent_level(2) + "selector:\n"
        retval += write_indent_level(3) + "matchLabels:\n"
        retval += write_indent_level(4) + f"name: {pod_name}-{i}\n"
        retval += write_indent_level(2) + "template:\n"
        retval += write_indent_level(3) + "metadata:\n"
        retval += write_indent_level(4) + "labels:\n"
        retval += write_indent_level(5) + f"name: {pod_name}-{i}\n"
        retval += write_indent_level(3) + "spec:\n"
        retval += write_indent_level(4) + "containers:\n"

        # TP
        retval += write_indent_level(5) + "- name: sawtooth-intkey-tp-python\n"
        retval += write_indent_level(6) + f"image: hyperledger/sawtooth-intkey-tp-python:chime\n"
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + '- "intkey-tp-python -vvv -C tcp://$HOSTNAME:4004"\n'
        retval += "\n"
        # Engine
        retval += write_indent_level(5) + f"- name: sawtooth-{pod_name}-engine\n"
        retval += write_indent_level(6) + f"image: {engines[pod_name]['image']}\n"
        retval += write_indent_level(6) + "imagePullPolicy: Never\n"
        retval += write_indent_level(6) + "ports:\n"
        retval += write_indent_level(7) + "- name: rpc\n"
        retval += write_indent_level(8) + "containerPort: 50051\n"

        retval += write_indent_level(6) + 'workingDir: "/project/consensus/"\n'
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + f'- "{engines[pod_name]["command"]}" \n'
        retval += "\n"

        # Rest api
        retval += write_indent_level(5) + "- name: sawtooth-rest-api\n"
        retval += write_indent_level(6) + "image: hyperledger/sawtooth-rest-api:chime\n"
        retval += write_indent_level(6) + "ports:\n"
        retval += write_indent_level(7) + "- name: api\n"
        retval += write_indent_level(8) + "containerPort: 8008\n"
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + '- "sawtooth-rest-api -vvv -C tcp://$HOSTNAME:4004 -B 0.0.0.0:8008"\n'
        retval += write_indent_level(6) + "readinessProbe:\n"
        retval += write_indent_level(7) + "httpGet:\n"
        retval += write_indent_level(8) + "path: /status\n"
        retval += write_indent_level(8) + "port: 8008\n"
        retval += write_indent_level(7) + "initialDelaySeconds: 30\n"
        retval += write_indent_level(7) + "periodSeconds: 10\n"
        retval += "\n"

        # Transaction processor
        retval += write_indent_level(5) + "- name: sawtooth-settings-tp\n"
        retval += write_indent_level(6) + "image: hyperledger/sawtooth-settings-tp:chime\n"
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + '- "settings-tp -vvv -C tcp://$HOSTNAME:4004"\n'
        retval += "\n"
        # Shell (jic)
        retval += write_indent_level(5) + "- name: sawtooth-shell\n"
        retval += write_indent_level(6) + "image: hyperledger/sawtooth-shell:chime\n"
        retval += write_indent_level(6) + "command:\n"
        retval += write_indent_level(7) + "- bash\n"
        retval += write_indent_level(6) + "args:\n"
        retval += write_indent_level(7) + "- -c\n"
        retval += write_indent_level(7) + '- "sawtooth keygen && tail -f /dev/null"\n'
        retval += "\n"

        # Big one (VALIDATOR)
        retval += write_indent_level(5) + "- name: sawtooth-validator\n"
        retval += write_indent_level(6) + "image: hyperledger/sawtooth-validator:chime\n"
        retval += write_indent_level(6) + "ports:\n"
        retval += write_indent_level(7) + "- name: tp\n"
        retval += write_indent_level(8) + "containerPort: 4004\n"
        retval += write_indent_level(7) + "- name: consensus\n"
        retval += write_indent_level(8) + "containerPort: 5050\n"
        retval += write_indent_level(7) + "- name: validators\n"
        retval += write_indent_level(8) + "containerPort: 8800\n"

        if i == 0:
            retval += write_indent_level(6) + "envFrom:\n"
            retval += write_indent_level(7) + "- configMapRef:\n"
            retval += write_indent_level(9) + "name: keys-config\n"
            retval += write_indent_level(6) + "command:\n"
            retval += write_indent_level(7) + "- bash\n"
            retval += write_indent_level(6) + "args:\n"
            retval += write_indent_level(7) + "- -c\n"
            retval += write_indent_level(7) + "- |\n"
            retval += write_indent_level(9) + "if [ ! -e /etc/sawtooth/keys/validator.priv ]; then\n"
            retval += write_indent_level(10) + "echo $ddpoa0priv > /etc/sawtooth/keys/validator.priv\n"
            retval += write_indent_level(10) + "echo $ddpoa0pub > /etc/sawtooth/keys/validator.pub\n"
            retval += write_indent_level(9) + "fi &&\n"
            retval += write_indent_level(9) + "if [ ! -e /root/.sawtooth/keys/my_key.priv ]; then\n"
            retval += write_indent_level(10) + "sawtooth keygen my_key\n"
            retval += write_indent_level(9) + "fi &&\n"
            retval += write_indent_level(9) + "if [ ! -e config-genesis.batch ]; then\n"
            retval += write_indent_level(
                10) + "sawset genesis -k /root/.sawtooth/keys/my_key.priv -o config-genesis.batch\n"
            retval += write_indent_level(9) + "fi &&\n"
            retval += write_indent_level(9) + "sleep 2 &&\n"

            retval += write_indent_level(9) + "if [ ! -e config.batch ]; then\n"
            retval += write_indent_level(10) + 'sawset proposal create \\\n'
            retval += write_indent_level(11) + '-k /root/.sawtooth/keys/my_key.priv \\\n'
            retval += write_indent_level(11) + f'sawtooth.consensus.algorithm.name={pod_name}\\\n'
            retval += write_indent_level(11) + f'sawtooth.consensus.algorithm.version={engines[pod_name]["version"]} \\\n'
            
            # Member public keys
            retval += write_indent_level(11) + f'sawtooth.consensus.{pod_name}.members=["'
            for node in range(num_pods):
                retval += f'\\"$ddpoa{node}pub\\"' + (',' if node < num_pods - 1 else '')            
            retval += '"] \\\n'

            # Member IP-addresses
            retval += write_indent_level(11) + f'sawtooth.consensus.{pod_name}.member_ips=['
            ips = [f'\\"$SAWTOOTH_{j}_SERVICE_HOST\\"' for j in range(num_pods)]
            # ips.remove(ips[i])
            retval += ",".join(ips) + "]" + "\\\n"

            retval += write_indent_level(11) + "sawtooth.publisher.max_batches_per_block=1200 \\\n"
            retval += write_indent_level(11) + f"sawtooth.consensus.ddpoa.slots={SLOTS} \\\n"
            retval += write_indent_level(11) + "-o config.batch\n"
            retval += write_indent_level(9) + "fi && \\\n"
            retval += write_indent_level(9) + "if [ ! -e /var/lib/sawtooth/genesis.batch ]; then\n"
            retval += write_indent_level(10) + "sawadm genesis config-genesis.batch config.batch\n"
            retval += write_indent_level(9) + "fi &&\n"
            retval += write_indent_level(9) + "sawtooth-validator -vvv \\\n"
            retval += write_indent_level(10) + "--endpoint tcp://$SAWTOOTH_0_SERVICE_HOST:8800 \\\n"
            retval += write_indent_level(10) + "--bind component:tcp://eth0:4004 \\\n"
            retval += write_indent_level(10) + "--bind consensus:tcp://eth0:5050 \\\n"
            retval += write_indent_level(10) + "--bind network:tcp://eth0:8800 \\\n"
            retval += write_indent_level(10) + "--scheduler parallel \\\n"
            retval +=write_indent_level(10) + f"--opentsdb-url http://${str(pod_name).upper()}_ADMIN_SERVICE_HOST:8086  \\\n"
            retval += write_indent_level(10) + "--opentsdb-db metrics \\\n"
            retval += write_indent_level(10) + "--peering static\\\n"
            retval += write_indent_level(10) + "--maximum-peer-connectivity 10000\n"
        else:
            retval += write_indent_level(6) + "env:\n"
            retval += write_indent_level(7) + f"- name: ddpoa{i}priv\n"
            retval += write_indent_level(8) + "valueFrom:\n"
            retval += write_indent_level(9) + "configMapKeyRef:\n"
            retval += write_indent_level(10) + "name: keys-config\n"
            retval += write_indent_level(10) + f"key: ddpoa{i}priv\n"

            retval += write_indent_level(7) + f"- name: ddpoa{i}pub\n"
            retval += write_indent_level(8) + f"valueFrom:\n"
            retval += write_indent_level(9) + "configMapKeyRef:\n"
            retval += write_indent_level(10) + "name: keys-config\n"
            retval += write_indent_level(10) + f"key: ddpoa{i}pub\n"

            retval += write_indent_level(6) + "command:\n"
            retval += write_indent_level(7) + "- bash\n"
            retval += write_indent_level(6) + "args:\n"
            retval += write_indent_level(7) + "- -c\n"
            retval += write_indent_level(7) + "- |\n"
            retval += write_indent_level(9) + "if [ ! -e /etc/sawtooth/keys/validator.priv ]; then\n"
            retval += write_indent_level(10) + f"echo $ddpoa{i}priv > /etc/sawtooth/keys/validator.priv\n"
            retval += write_indent_level(10) + f"echo $ddpoa{i}pub > /etc/sawtooth/keys/validator.pub \n"
            retval += write_indent_level(9) + "fi && \n"
            retval += write_indent_level(9) + "sleep 3 && \n"
            retval += write_indent_level(9) + "sawtooth keygen my_key && \n"
            retval += write_indent_level(9) + "sawtooth-validator -vvv \\\n"
            retval += write_indent_level(10) + f"--endpoint tcp://$SAWTOOTH_{i}_SERVICE_HOST:8800 \\\n"
            retval += write_indent_level(10) + "--bind component:tcp://eth0:4004 \\\n"
            retval += write_indent_level(10) + "--bind consensus:tcp://eth0:5050 \\\n"
            retval += write_indent_level(10) + "--bind network:tcp://eth0:8800 \\\n"
            retval +=write_indent_level(10) + f"--opentsdb-url http://${str(pod_name).upper()}_ADMIN_SERVICE_HOST:8086  \\\n"
            retval += write_indent_level(10) + "--opentsdb-db metrics \\\n"
            retval += write_indent_level(10) + "--scheduler parallel \\\n"
            retval += write_indent_level(10) + "--peering static\\\n"
            retval += write_indent_level(10) + "--maximum-peer-connectivity 10000 \\\n"
            retval += write_indent_level(10) + "--peers \\\n"  
            
            for j in range(0,num_pods):
                if j == i:
                    continue
                retval += write_indent_level(10) + ("" if j == 0 else ", ") + f" tcp://$SAWTOOTH_{j}_SERVICE_HOST:8800 "
                retval += "\\\n" if j != i - 1 else "\n"
        
        retval += "- apiVersion: v1\n"
        retval += write_indent_level(1) + "kind: Service\n"
        retval += write_indent_level(1) + "metadata:\n"
        retval += write_indent_level(2) + f"name: sawtooth-{i}\n"
        retval += write_indent_level(1) + "spec:\n"
        retval += write_indent_level(2) + "type: ClusterIP\n"
        retval += write_indent_level(2) + "selector:\n"
        retval += write_indent_level(3) + f"name: {pod_name}-{i}\n"
        retval += write_indent_level(2) + "ports:\n"
        retval += write_indent_level(3) + '- name: "4004"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 4004\n'
        retval += write_indent_level(4) + 'targetPort: 4004\n'

        retval += write_indent_level(3) + '- name: "5050"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 5050\n'
        retval += write_indent_level(4) + 'targetPort: 5050\n'

        retval += write_indent_level(3) + '- name: "8008"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 8008\n'
        retval += write_indent_level(4) + 'targetPort: 8008\n'

        retval += write_indent_level(3) + '- name: "8080"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 8080\n'
        retval += write_indent_level(4) + 'targetPort: 8080\n'

        retval += write_indent_level(3) + '- name: "50051"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 50051\n'
        retval += write_indent_level(4) + 'targetPort: 50051\n'

        retval += write_indent_level(3) + '- name: "8800"\n'
        retval += write_indent_level(4) + 'protocol: TCP\n'
        retval += write_indent_level(4) + 'port: 8800\n'
        retval += write_indent_level(4) + 'targetPort: 8800\n'
        retval += "\n"

    return retval


def create_kubernetes_file():

    engine = args.engine

    with open("kubernetes_test_file.yml", "w") as outfile:
        outfile.write("---\n")
        outfile.write("apiVersion: v1\n")
        outfile.write("kind: List\n")
        outfile.write("\n")
        outfile.write("items:\n")
        outfile.write("\n\n")

        #outfile.write("services:\n")
        outfile.write(create_custom_sawtooth_pod(NUM_CONSENSUS_NODES, engine) + create_admin_pod(engine,NUM_CONSENSUS_NODES))
    
    with open("workload_test_file.yml","w") as outfile:
        outfile.write("---\n")
        outfile.write("apiVersion: v1\n")
        outfile.write("kind: List\n")
        outfile.write("\n")
        outfile.write("items:\n")
        outfile.write("\n\n")

        outfile.write(create_workload_pod(engine,NUM_CONSENSUS_NODES)) 


if __name__ == '__main__':
    # NUM_CONSENSUS_NODES = 32
    #create_docker_compose_file()
    create_kubernetes_file()
