import logging
import time
from typing import Dict, List
from threading import Thread

from .consensus_messaging import Communicator
from .config import PEER_CHECK_INTERVAL, PING_THRESHOLD
from .types import Key
from ..consensus.service_pb2 import ConsensusMessage, MessageType, Bootstrap

LOGGER = logging.getLogger(__name__)


class PeerNode:
    def __init__(self, key: Key):
        self.key: Key = key
        self.score: float = 1.0
        self.last_seen: float = time.time()
        self.online: bool = False

    def seen(self):
        self.online = True
        self.last_seen = time.time()

    def set_online(self, online: bool):
        self.online = online

    def __repr__(self) -> str:
        return f"peer({self.key}, online={self.online})"


class ConsensusNode:
    def __init__(self, key: str, peer_keys: List[Key]):
        self.key: str = key
        self.peers: Dict[str, PeerNode] = {}
        self.peer_keys = peer_keys
        for peer in peer_keys:
            self.add_peer(peer)

        self.peers[self.key].set_online(True)
        self.last_peer_check: float = 0

        self._communicator = Communicator()
        rpc_thread = Thread(target=self._communicator.server, args=())
        rpc_thread.start()

    def add_peer(self, peer_key: Key):
        if not self.peers.get(peer_key, False):
            self.peers[peer_key] = PeerNode(peer_key)

    def remove_peer(self, peer_key: Key):
        if peer_key in self.peers:
            self.peers[peer_key].set_online(False)

    def peer_connected(self, peer_key: Key, peer_ip: str):
        self._communicator.add_peer(peer_key, peer_ip)

    def check_on_peers(self):
        now = time.time()
        if now - self.last_peer_check > PEER_CHECK_INTERVAL:
            for peer in self.peers.values():
                if peer.key == self.key:
                    continue

                if now - peer.last_seen >= PING_THRESHOLD:
                    if self.send_ping(peer.key):
                        peer.seen()
                    else:
                        self.remove_peer(peer.key)
            self.last_peer_check = now

    def seen(self, peer_key):
        self.peers[peer_key].seen()

    ### OUTGOING MESSAGES ###

    def send_ping(self, peer_key) -> bool:
        return self._communicator.ping(peer_key)

    def send_bootstrap_message(self, peer_key, chain_head_id, num_blocks, pre_id):
        boot = Bootstrap()
        boot.chain_head_id = chain_head_id
        boot.num_blocks = num_blocks
        boot.pre_id = pre_id
        msg = ConsensusMessage(type=MessageType.BOOTSTRAP, bootstrap=boot)
        self.send_to(peer_key, msg)

    def send_bootstrap_request(self, peer_key):
        msg = ConsensusMessage(type=MessageType.BOOTSTRAP_REQUEST)
        self.send_to(peer_key, msg)

    ### UTILITIES ###

    def broadcast(self, msg):
        msg.timestamp = int(time.time())
        msg.signer = self.key
        self._communicator.broadcast(msg)

    def send_to(self, peer_key: Key, msg):
        msg.timestamp = int(time.time())
        msg.signer = self.key
        self._communicator.send(peer_key, msg)
