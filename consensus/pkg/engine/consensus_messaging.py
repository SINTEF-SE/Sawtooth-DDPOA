from concurrent import futures
from threading import Thread, Timer
from time import sleep
import grpc
import queue
import logging
from functools import reduce

import pkg.consensus.service_pb2 as service_pb2
import pkg.consensus.service_pb2_grpc as service_pb2_grpc

LOGGER = logging.getLogger(__name__)


class ConsensusRPC(service_pb2_grpc.ConsensusRPCServicer):
    def __init__(self, queue) -> None:
        super().__init__()
        self.queue = queue

    def Message(self, request, context):
        self.queue.put(request)
        return service_pb2.Empty()   # type: ignore

    def Ping(self, request, context):
        return service_pb2.Empty()   # type: ignore


class Communicator:
    def __init__(self):
        self._peers: dict[str, Peer] = {}
        self.queue = queue.Queue()

    def online_peers(self) -> int:
        return reduce(
            lambda acc, p: acc + 1 if p.connected else acc, self._peers.values(), 0
        )

    def add_peer(self, peer_key, peer_ip):
        if (peer := self._peers.get(peer_key)) is not None:
            if not peer.ping():
                peer.channel.close()
                del peer
                self._peers[peer_key] = Peer(peer_ip)
        else:
            self._peers[peer_key] = Peer(peer_ip)

    def recv(self):
        try:
            msg = self.queue.get_nowait()
            return msg
        except queue.Empty:
            return None

    def ping(self, peer_key) -> bool:
        if peer_key in self._peers:
            return self._peers[peer_key].ping()
        else:
            return False

    def send(self, to, msg):
        return self._peers[to].send(msg)

    def broadcast(self, msg):
        threads = []
        for peer in self._peers.values():
            if peer.connected:
                t = Thread(target=peer.send, args=(msg,))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()
        del threads

    def server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        service_pb2_grpc.add_ConsensusRPCServicer_to_server(
            ConsensusRPC(self.queue), server
        )
        server.add_insecure_port("[::]:50051")
        server.start()
        server.wait_for_termination()


class Peer:
    def __init__(self, ip):
        self.connected = False
        connect_timer = Timer(3.0, self.connect, (ip,))  # Give peer time to start consensus engine
        connect_timer.start()

    def connect(self, ip):
        self.channel = grpc.insecure_channel(f"{ip}:50051")
        self.stub = service_pb2_grpc.ConsensusRPCStub(self.channel)

        while not self.ping():
            sleep(0.5)

    def ping(self):
        try:
            _ = self.stub.Ping(service_pb2.Empty())  # type: ignore
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    def send(self, msg):
        if self.connected:
            try:
                _ = self.stub.Message(msg)
            except Exception:
                LOGGER.debug("NODE IS UNAVAILABLE")
