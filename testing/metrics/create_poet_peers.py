

from sys import argv

prefix, suffix = "--peers tcp:\/\/$SAWTOOTH_" , "_SERVICE_HOST:8800 "


NODES = 16
current_peer = int(argv[1])

def create_peer_list():
    peer_list = ""
    for i in range(1, NODES):
        if i != current_peer:
            peer_list += prefix + str(i) + suffix
    return peer_list

if __name__ == "__main__":
    print(create_peer_list())
