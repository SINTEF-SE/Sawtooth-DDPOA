import json
import logging
from operator import itemgetter
import queue
import time
from typing import Dict, List, Tuple

from sawtooth_sdk.consensus import exceptions
from sawtooth_sdk.consensus.engine import Engine
from sawtooth_sdk.consensus.service import Block
from sawtooth_sdk.consensus.zmq_service import ZmqService
from sawtooth_sdk.protobuf.validator_pb2 import Message

from .utils import try_remove
from .config import BLOCK_INTERVAL, GENESIS_BLOCK_ID, SLOT_TIMEOUT
from .ddpoa_node import DDPoANode, State

from ..consensus.consensus_data_pb2 import ConsensusData  # type: ignore
from ..consensus.service_pb2 import MessageType, Bootstrap  # type: ignore

LOGGER = logging.getLogger(__name__)


class DDPoAEngine(Engine):
    def __init__(self, path_config, component_endpoint):
        self._path_config = path_config
        self._component_endpoint = component_endpoint
        self._service: ZmqService
        self._node: DDPoANode
        self.local_id: bytes
        self.block_cache: BlockCache
        self.members: List[str]
        self.pre_committed_block: Tuple[bytes, int]

        self._exit = False
        self._slot_started_at = time.time()
        self._waiting_for_own_block: bool = False
        self._waiting_for_commit: int = 0
        self._waiting_for_validation: int = 0

        # Catch up parametrers
        self.bootstrap_messages_received: List[Bootstrap] = []
        self._bootstrap_cache: Dict[str, Block] = {}
        self.fastforward_target: int = None  # type: ignore
        self.num_slots = None
        self._has_requested_bootstrap = False
        self._pre_bootstrap_request = time.time()

    def name(self):  # pylint: disable=invalid-overridden-method
        return "ddpoa"

    def version(self):  # pylint: disable=invalid-overridden-method
        return "0.1"

    def additional_protocols(self):
        return [(self.name(), self.version())]

    def stop(self):
        self._exit = True

    def start(self, updates, service: ZmqService, startup_state):
        LOGGER.info(msg="DDPoA Engine starting...")

        self._service = service
        self.block_cache = BlockCache(service)
        self.local_id = startup_state.local_peer_info.peer_id

        settings = self._service.get_settings(
            startup_state.chain_head.block_id,
            [
                "sawtooth.consensus.ddpoa.members",
                "sawtooth.consensus.ddpoa.slots",
                "sawtooth.consensus.ddpoa.member_ips",
            ],
        )

        self.members = json.loads(
            settings["sawtooth.consensus.ddpoa.members"].replace("'", '"')
        )

        ips = json.loads(
            settings["sawtooth.consensus.ddpoa.member_ips"].replace("'", '"')
        )

        self.ips = {k: v for k, v in zip(self.members, ips)}
        self.num_slots = int(settings["sawtooth.consensus.ddpoa.slots"])

        self._node = DDPoANode(self.local_id.hex(), self.members, self.num_slots)  # type: ignore

        handlers = {
            Message.CONSENSUS_NOTIFY_BLOCK_NEW: self._handle_new_block,  # type: ignore
            Message.CONSENSUS_NOTIFY_BLOCK_VALID: self._handle_valid_block,  # type: ignore
            Message.CONSENSUS_NOTIFY_BLOCK_INVALID: self._handle_invalid_block,  # type: ignore
            Message.CONSENSUS_NOTIFY_BLOCK_COMMIT: self._handle_committed_block,  # type: ignore
            Message.CONSENSUS_NOTIFY_PEER_CONNECTED: self._handle_peer_connected,  # type: ignore
            Message.CONSENSUS_NOTIFY_PEER_DISCONNECTED: self._handle_peer_disconnected,  # type: ignore
        }

        if startup_state.chain_head.previous_id == GENESIS_BLOCK_ID:
            LOGGER.info("Genesis block detected")
        else:
            LOGGER.info("Non-genesis block detected")
            # For reasons unknown, sawtooth doesnt really believe in anything and therefore we have to assume we are catching up here
            # This sadly makes us blindly commit first block and from there we can potentially check consensus rules
            self._node.state = State.WAITING_FOR_BOOTSTRAP

        self.block_cache.append(startup_state.chain_head)
        self.pre_committed_block = (
            startup_state.chain_head.block_id,
            startup_state.chain_head.block_num,
        )

        LOGGER.info(
            "My activation message gave me the following chainhead: %s\n \
            and the head has LENGTH: %i",
            startup_state.chain_head.block_id.hex(),
            startup_state.chain_head.block_num,
        )

        LOGGER.debug(
            "members:\n"
            + "\n".join([f"{i}: {m[:5]}" for i, m in enumerate(self.members)])
        )

        now: float = time.time()
        pre_bootstrap_request: float = now
        engine_start: float = now
        starting_up: bool = True

        while True:
            try:
                # Handle sawtooth/blockchain messages
                try:
                    type_tag, data = updates.get(timeout=0.08)
                except queue.Empty:
                    pass
                else:
                    try:
                        handle_message = handlers[type_tag]
                    except KeyError:
                        LOGGER.error(
                            "Unknown type tag: %s", Message.MessageType.Name(type_tag)  # type: ignore
                        )
                    else:
                        handle_message(data)

                # Handle consensus messages (DDPoA logic)
                if (msg := self._node.recv()) is not None:
                    self._handle_peer_msgs(msg)

                if self._exit:
                    break

                # When starting a new network wait a minute to let members start up and connect
                if starting_up:
                    starting_up = (
                        self._node.state != State.WAITING_FOR_BOOTSTRAP
                        and (self._node.online_peers != len(self.members))
                        and (time.time() - engine_start < 70)
                    )
                    continue

                if self._node.state not in (
                    State.WAITING_FOR_BOOTSTRAP,
                    State.CATCHING_UP,
                ):
                    if (
                        self._node.state != State.IDLE
                        and self._waiting_for_validation == 0
                    ):
                        if self.time_for_next_block():
                            if self._node.is_current_witness and not self.waiting():
                                if self._summarize_block() is not None:
                                    self._finalize_block()
                                else:
                                    LOGGER.debug("Broadcasting EMPTY_SLOT message")
                                    self._node.broadcast_empty_slot()
                                    self._next_slot(int(time.time()))

                            if self.slot_is_missed() and self._node.state in (
                                State.PRODUCTION,
                                State.ELECTION,
                            ):
                                peer = self._node.expected_signer
                                LOGGER.debug(
                                    f"SLOT WAS MISSED by {self.members.index(peer)} / {peer[:5]}"
                                )
                                self.handle_missed_slot()

                    if self._node.should_vote:
                        self._node.vote()
                    elif self._node.should_rebroadcast_ballot:
                        self._node.rebroadcast_ballot()

                    self._node.check_on_peers()

                if (
                    self._node.state == State.WAITING_FOR_BOOTSTRAP
                    and time.time() - pre_bootstrap_request > 5
                ):
                    for peer in self._node.peers:
                        self._node.send_bootstrap_request(peer)
                    pre_bootstrap_request = time.time()

            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unhandled exception in message loop")

    def time_for_next_block(self) -> bool:
        return time.time() - self._slot_started_at > BLOCK_INTERVAL

    def waiting(self):
        return (
            self._waiting_for_own_block
            or (self._waiting_for_validation > 0)
            or (self._waiting_for_commit > 0)
        )

    def slot_is_missed(self) -> bool:
        timeout = time.time() - self._slot_started_at > (BLOCK_INTERVAL + SLOT_TIMEOUT)
        return timeout and not self.waiting() and self._node.epoch.is_initialized

    def handle_missed_slot(self):
        self._node.penalize(self._node.expected_signer)
        self._node.downgrade(self._node.expected_signer)
        self._next_slot(int(time.time()))

    def _summarize_block(self):
        try:
            return self._service.summarize_block()
        except exceptions.InvalidState as err:
            LOGGER.warning(err)
            return None
        except exceptions.BlockNotReady:
            return None

    def _finalize_block(self):
        # ConsensusData is the payload in Block (handled in _handle_new_block)
        # TODO: Add total reputation (sum of reputation for the nodes that voted or
        #       sent a signed message directly to the block creator)
        consensus = ConsensusData(
            timestamp=int(time.time()),
            epoch=self._node.epoch.number,
            witnessIdx=self._node.epoch.current_witness_idx,
            candidates=self._node.epoch.full_candidate_list,
            num_slots=self._node.epoch.num_slots,
            consensus=f"{self.name()}:{self.version()}",
        )  ## Might want to put some of this info in the bootstrap message instead

        try:
            block_id = self._service.finalize_block(consensus.SerializeToString())
            self._waiting_for_own_block = True
            LOGGER.debug("Finalized %s", block_id.hex()[:10])
            return block_id

        except exceptions.BlockNotReady:
            LOGGER.debug("Block not ready to be finalized")
            return None

        except exceptions.InvalidState:
            LOGGER.warning("block cannot be finalized")
            return None

    def _try_cancel(self):
        try:
            self._service.cancel_block()
        except exceptions.InvalidState:
            pass

    def _next_slot(self, start_ts):
        self._node.next_slot(self.pre_committed_block[0].hex())
        self._slot_started_at = start_ts
        self._try_cancel()
        if self._node.is_current_witness:
            self._service.initialize_block()

    def fastforward(self, target_id: bytes, target_num: int):
        pre_id, pre_num = self.pre_committed_block
        if target_id == pre_id:
            self._has_requested_bootstrap = False
            self.bootstrap_messages_received = []
            return

        # TODO : Priority queue - blocks received while fast forwarding need to be checked after the "fast forward"-blocks
        if self._node.state != State.CATCHING_UP:
            LOGGER.info(
                "Starting FastForwarding to block %i | %s",
                target_num,
                target_id.hex()[:5],
            )
            self._node.state = State.CATCHING_UP
            self.fastforward_target = target_num
            self.fastforward_target_id = target_id

            if self.block_cache.block_from_id(target_id):
                if self.block_cache.traversable(target_id, pre_id):
                    # Lagging behind (probably received a block later than the rest of the network)
                    block_ids = self.block_cache.block_path(target_id, pre_id)
                    self._waiting_for_validation += len(block_ids)
                    self._service.check_blocks(block_ids)
                else:
                    # A fork has happened
                    longest_chain = self.block_cache.longest_chain(target_id)
                    common_block, forked_block = self.common_and_forked_block(
                        longest_chain
                    )  # The block on our chain that is incompatible with the consensus chain

                    if common_block and forked_block:
                        LOGGER.info(
                            f"pre common block: {common_block.hex()[:5]} | forked_block: {forked_block.hex()[:5]}"
                        )
                        LOGGER.info(
                            f"Failing committed block: {forked_block.hex()[:5]}"
                        )
                        self._service.fail_block(forked_block)
                        new_fork = longest_chain[longest_chain.index(common_block):]
                        try_remove(new_fork, pre_id)
                        try_remove(new_fork, common_block)
                        self._waiting_for_validation += len(new_fork)
                        self._service.check_blocks(new_fork)

            elif target_id in self._bootstrap_cache.values():
                block_ids = [
                    (b.block_id, b.block_num) for b in self._bootstrap_cache.values()
                ]
                block_ids.sort(key=lambda b: b[1])
                self._waiting_for_validation += len(block_ids)
                self._service.check_blocks([b[0] for b in block_ids])

    def common_and_forked_block(self, chain: List[bytes]):
        cur_block = self._service.get_chain_head()
        for _ in range(10):
            pre_id = cur_block.previous_id
            if pre_id in chain:
                return (pre_id, cur_block.block_id)
            cur_block = self._service.get_blocks([pre_id])[pre_id]
        return (None, None)

    def _handle_new_block(self, block: Block):
        signer = block.signer_id.hex()

        LOGGER.debug(
            "HANDLING NEW BLOCK | num: %i | id: %s | signer: %s",
            block.block_num,
            block.block_id.hex()[:10],
            signer[:5],
        )

        if signer not in self.members:
            self._service.fail_block(block.block_id)
            return

        consensus = ConsensusData()
        consensus.ParseFromString(block.payload)

        if time.time() < consensus.timestamp:
            LOGGER.warning(
                "Timestamp in blocks consensus data was invalid (higher than current time)"
            )
            self._node.penalize(block.signer_id.hex())
            self._service.fail_block(block.block_id)
            return

        self._node.seen(signer)
        self.block_cache.append(block)

        pre_id, pre_num = self.pre_committed_block
        if block.previous_id == pre_id and block.block_num == pre_num + 1:
            if signer == self._node.expected_signer:
                if self._waiting_for_own_block:
                    self._waiting_for_own_block = block.signer_id != self.local_id
                self._waiting_for_validation += 1
                self._service.check_blocks([block.block_id])

        if self._node.state == State.WAITING_FOR_BOOTSTRAP:
            self._bootstrap_cache[block.block_id.hex()] = block
            return
        elif self._node.state == State.CATCHING_UP and self.block_cache.traversable(
            block.block_id, self.fastforward_target_id
        ):
            self._waiting_for_validation += 1
            self._service.check_blocks([block.block_id])
            return

        if block.block_num > pre_num + 1 and not self.waiting():
            if self.block_cache.traversable(block.previous_id, pre_id):
                LOGGER.debug(
                    "Was able to traverse through block cache even if block was not next one. I might be desynced!"
                )
            else:
                LOGGER.debug(
                    "Was NOT able to traverse through block cache. A fork has happened"
                )
            if (
                time.time() - self._pre_bootstrap_request > 6
                or not self._has_requested_bootstrap
            ):
                self._pre_bootstrap_request = time.time()
                self._has_requested_bootstrap = True
                self._node.broadcast_bootstrap_request()

    def _handle_valid_block(self, block_id):
        LOGGER.debug(msg=f"HANDLING VALID BLOCK {block_id.hex()[:10]}")
        block = self._service.get_blocks([block_id])[block_id]
        self._waiting_for_validation -= 1
        pre_id, pre_num = self.pre_committed_block

        if self._node.state == State.CATCHING_UP and block.previous_id == pre_id:
            self._service.commit_block(block_id)
            return

        correct_signer = block.signer_id.hex() == self._node.expected_signer
        correct_id = block.previous_id == pre_id
        correct_num = block.block_num == pre_num + 1

        if correct_signer and correct_id and correct_num:
            self._waiting_for_commit += 1
            self._service.commit_block(block_id)
        else:
            LOGGER.debug(
                f"Failing block after validation: {block_id.hex()[:5]}\n sign: {correct_signer} | id: {correct_id} | num: {correct_num}"
            )
            self._service.fail_block(block_id)

    def _handle_invalid_block(self, block_id):
        LOGGER.info(msg=f"HANDLING INVALID BLOCK: {block_id.hex()[:10]}")
        if (block := self.block_cache.block_from_id(block_id)) is None:
            block = self._service.get_blocks([block_id])[block_id]
        consensus = ConsensusData()
        consensus.ParseFromString(block.payload)
        self._node.penalize(block.signer_id.hex())
        self._node.downgrade(block.signer_id.hex())
        self._next_slot(consensus.timestamp)
        self._waiting_for_validation -= 1

    def _handle_committed_block(self, block_id):
        try:
            block = self._bootstrap_cache[block_id.hex()]
        except KeyError:
            if (block := self.block_cache.block_from_id(block_id)) is None:
                block = self._service.get_blocks([block_id])[block_id]

        if not block:
            LOGGER.info(
                "Committed block not found in _service, block_cache, or _bootstrap_cache!"
            )
        else:
            LOGGER.info(
                "HANDLING COMMITED BLOCK num: %i | id: %s",
                block.block_num,
                block_id.hex()[:10],
            )

        consensus = ConsensusData()
        consensus.ParseFromString(block.payload)

        self.pre_committed_block = (block.block_id, block.block_num)
        self._node.reward(block.signer_id.hex())
        self._waiting_for_commit -= 1

        if self._node.state == State.CATCHING_UP:
            if block.block_num == self.fastforward_target:
                self._node.bootstrap(
                    consensus.epoch,
                    consensus.witnessIdx,
                    consensus.candidates,
                    consensus.num_slots,
                )
                self.bootstrap_messages_received = []
                self._has_requested_bootstrap = False

        self._next_slot(consensus.timestamp)

        if next_block := self.block_cache.block_by_num_and_signer(
            block.block_num + 1, self._node.expected_signer
        ):
            self._waiting_for_validation += 1
            self._service.check_blocks([next_block.block_id])

    def _handle_peer_msgs(self, msg):
        consensus_msg = msg
        signer_id = msg.signer

        if signer_id not in self.members:
            return

        self._node.seen(signer_id)

        if consensus_msg.type == MessageType.VOTE:
            self._node.handle_vote(consensus_msg, signer_id)

        elif consensus_msg.type == MessageType.VOTE_RESULT:
            LOGGER.debug(f"Received vote result from {msg.signer[:5]}")
            new_epoch = self._node.handle_vote_result(consensus_msg, signer_id)
            if new_epoch:
                self._slot_started_at = time.time()

        elif consensus_msg.type == MessageType.EMPTY_SLOT:
            LOGGER.debug(f"Received empty slot from {msg.signer[:5]}")
            if signer_id == self._node.expected_signer:
                self._next_slot(consensus_msg.timestamp)

        elif consensus_msg.type == MessageType.BOOTSTRAP_REQUEST:
            LOGGER.debug(f"\n\nReceived BOOTSTRAP_REQUEST from {msg.signer[:5]}\n\n")
            head = self._service.get_chain_head()
            self._node.send_bootstrap_message(
                signer_id, head.block_id, head.block_num, head.previous_id
            )

        elif consensus_msg.type == MessageType.BOOTSTRAP:
            LOGGER.debug(
                "\n\t--- Received BOOTSTRAP message ---\t block_num: %i | block_id: %s",
                consensus_msg.bootstrap.num_blocks,
                consensus_msg.bootstrap.chain_head_id.hex()[:10],
            )
            self.bootstrap_messages_received.append(consensus_msg.bootstrap)

            blocks = {}
            for m in self.bootstrap_messages_received:
                if block := blocks.get(m.chain_head_id):
                    block["count"] += 1
                else:
                    blocks[m.chain_head_id] = {"num": m.num_blocks, "count": 1}
                if block := blocks.get(m.pre_id):
                    block["count"] += 1
                else:
                    blocks[m.pre_id] = {"num": m.num_blocks - 1, "count": 1}

            blocks = [(k, v["num"], v["count"]) for k, v in blocks.items()]
            blocks.sort(key=itemgetter(2, 1), reverse=True)
            consensus_head = blocks[0]

            LOGGER.debug(f"Chain heads: {[(b[0].hex()[:5], b[1], b[2]) for b in blocks]}\nConsensus: {(consensus_head[0].hex()[:5], consensus_head[1], consensus_head[2])}")
            LOGGER.debug(f"consensus count: {consensus_head[2]} | min count: {self._node.voting.consensus_amount(self._node.online_peers) - 1}")
            if (
                consensus_head[2]
                >= (self._node.voting.consensus_amount(self._node.online_peers) - 1)
            ):
                self.fastforward(consensus_head[0], consensus_head[1])

            if len(self.bootstrap_messages_received) == self._node.online_peers - 1:
                self.bootstrap_messages_received = []
                self._has_requested_bootstrap = False

    def _handle_peer_connected(self, msg):
        peer_key = msg.peer_id.hex()
        LOGGER.info(
            msg=f"HANDLING PEER CONNECTED: {peer_key[:10]} | Is member: {peer_key in self.members}"
        )

        if self._node.state == State.WAITING_FOR_BOOTSTRAP:
            LOGGER.debug("Sending BOOTSTRAP_REQUEST")
            self._node.send_bootstrap_request(peer_key)

        self._node.peer_connected(peer_key, self.ips[peer_key])

    def _handle_peer_disconnected(self, msg):
        LOGGER.info(msg="HANDLING PEER DISCONNECTED")


class BlockCache:
    def __init__(self, service):
        self._service = service
        self._cache: Dict[bytes, Block] = {}
        self._cache_ids: List[bytes] = []

    def append(self, block: Block):
        self._cache_ids.append(block.block_id)
        self._cache[block.block_id] = block
        if len(self._cache_ids) > 10:
            id_to_pop = self._cache_ids.pop(0)
            self._cache.pop(id_to_pop)
            self._service.ignore_block(id_to_pop)

    def block_from_id(self, block_id) -> Block:
        return self._cache.get(block_id, None)  # type: ignore

    def block_by_num_and_signer(self, block_num: int, signer: str):
        for block in self._cache.values():
            if block.block_num == block_num and block.signer_id.hex() == signer:
                return block

    def traversable(self, from_id: bytes, to_id: bytes):
        prev: bytes = from_id
        while curr := self._cache.get(prev, None):
            if curr.block_id == to_id:
                return True
            prev = curr.previous_id
        return prev == to_id

    def contains(self, block_id: bytes):
        return block_id in self._cache_ids

    def block_path(self, from_id: bytes, to_id: bytes):
        block_ids = []
        cur_block = self._cache[from_id]
        while cur_block.previous_id != to_id:
            block_ids.append(cur_block.block_id)
            cur_block = self._cache[cur_block.previous_id]
        block_ids.append(cur_block.block_id)
        block_ids.reverse()
        return block_ids

    def longest_chain(self, from_id: bytes):
        block_ids = [from_id]
        cur_block = self._cache[from_id]
        while (block := self._cache.get(cur_block.previous_id, None)) is not None:
            block_ids.append(block.block_id)
            cur_block = block
        block_ids.reverse()
        return block_ids


def log_block(block):
    LOGGER.info(
        "Block("
        + ", ".join(
            [
                "block_num: {}".format(block.block_num),
                "block_id: {}".format(block.block_id.hex()),
                "previous_id: {}".format(block.previous_id.hex()),
                "signer_id: {}".format(block.signer_id.hex()),
                "payload: {}".format(block.payload),
                "summary: {}".format(block.summary.hex()),
            ]
        )
        + ")"
    )
