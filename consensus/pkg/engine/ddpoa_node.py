import logging
import threading
import time
from enum import IntEnum, unique
from typing import Dict, List

from pkg.consensus.service_pb2 import ConsensusMessage, MessageType # type: ignore
from .config import REBROADCAST_BALLOT_INTERVAL, VOTING_SLOTS
from .consensus_node import ConsensusNode
from .epoch import Epoch
from .types import Key
from .voting_system import VotingSystem

LOGGER = logging.getLogger(__name__)


@unique
class State(IntEnum):
    IDLE = 0
    ELECTION = 1
    PRODUCTION = 2
    WAITING_FOR_BOOTSTRAP = 3
    CATCHING_UP = 4


class DDPoANode(ConsensusNode):
    def __init__(self, key: str, peer_keys: List[Key], slots):
        super().__init__(key, peer_keys)
        self.epoch: Epoch = Epoch(0, slots=slots)
        self.state: State = State.IDLE
        self.voting = VotingSystem(Key(key), peer_keys, slots)
        self.previous_vote_ts: float = 0
        self.previous_result_ts: float = 0
        self.broadcast_timer: threading.Timer | None = None
        self.ready_result: Dict[int, bool] = {}
        self.num_slots = slots

        self._pre_online = 0

    def vote(self):
        """
        Fills a ballot and broadcasts it to the network
        """
        ballot = self.voting.fill_ballot(self.peers)
        self.voting.add_ballot(self.epoch.next_epoch_number, self.key, ballot) # type: ignore
        if self.state != State.CATCHING_UP:
            self.state = State.ELECTION
        msg = ConsensusMessage(
            type=MessageType.VOTE, votes=ballot, epoch=self.epoch.next_epoch_number
        )
        self.broadcast(msg)
        self.previous_vote_ts = time.time()

    @property
    def should_vote(self) -> bool:
        """
        Nodes should only vote when it has not already filled a ballot, and there are enough
        peers to send the ballot to.
        """
        is_before_first_epoch = self.epoch.number == 0

        if (
            self.epoch.slots_remaining_in_epoch <= VOTING_SLOTS or self.epoch.is_over
        ) or is_before_first_epoch:
            not_voted = not self.voting.has_voted(
                Key(self.key), self.epoch.next_epoch_number
            )
            enough_peers = self.online_peers > self.num_slots
            return enough_peers and not_voted

        return False

    @property
    def should_rebroadcast_ballot(self) -> bool:
        """
        Ballots should be rebroadcasted to ensure that slow nodes and newly
        connected nodes get the ballots.
        """
        votable_state = self.state == State.ELECTION
        timeout_reached = (
            time.time() - self.previous_vote_ts > REBROADCAST_BALLOT_INTERVAL
        )
        return votable_state and timeout_reached

    def rebroadcast_ballot(self):
        msg = ConsensusMessage(
            type=MessageType.VOTE,
            votes=self.voting.ballots[self.epoch.next_epoch_number][self.key], # type: ignore
            epoch=self.epoch.next_epoch_number,
        )
        self.broadcast(msg)
        self.previous_vote_ts = time.time()

    @property
    def online_peers(self) -> int:
        num_online = self._communicator.online_peers() + 1  # include self

        if num_online != self._pre_online:
            LOGGER.debug(f"Online peers: {num_online}")
            self._pre_online = num_online

        return num_online

    @property
    def is_current_witness(self):
        return self.epoch.current_witness == self.key

    @property
    def next_witness(self) -> Key:
        return self.epoch.next_witness

    @property
    def expected_signer(self) -> Key:
        """Returns the key of the witness that should sign the next block."""
        return self.epoch.current_witness

    def broadcast_result(self, epoch: int):
        LOGGER.debug(f"Broadcasting result for epoch {epoch}")
        result = self.voting.calculate_result(epoch)
        msg = ConsensusMessage(type=MessageType.VOTE_RESULT, result=result, epoch=epoch)
        self.broadcast(msg)

    def bootstrap(
        self, epoch_num: int, witness_idx: int, candidates: List[Key], num_slots: int
    ):
        self.num_slots = num_slots
        self.epoch = Epoch(epoch_num, num_slots)
        self.epoch.set_candidates_and_witnesses(candidates)
        self.epoch.current_witness_idx = witness_idx
        self.state = State.PRODUCTION

    def initialize_epoch(self, epoch: int):
        LOGGER.debug("Initializing epoch %i", epoch)

        self.epoch = Epoch(epoch, self.num_slots)
        if self.state != State.CATCHING_UP:
            self.state = State.PRODUCTION

        self.epoch.set_candidates_and_witnesses(
            self.voting.get_candidates(self.epoch.number) # type: ignore
        )

        if self.epoch.is_witness(self.key):  # type: ignore
            witness_number = self.epoch.position_in_witness_list(self.key)  # type: ignore
            LOGGER.info(
                "I am witness: %i in epoch %i", witness_number, self.epoch.number
            )

        self.voting.remove_old_epoch_data()

    def finalize_epoch(self):
        LOGGER.debug("Finalizing epoch %i", self.epoch.number)
        if self.state != State.CATCHING_UP:
            self.state = State.IDLE
        self.ready_result.pop(self.epoch.number - 2, None)

    def downgrade(self, peer_key: Key):
        LOGGER.info("Downgrading witness: %s", peer_key[:10])
        self.epoch.downgrade_witness(peer_key)

    def penalize(self, peer_key: Key):
        if peer_key == self.key:
            return
        LOGGER.info("Penalizing peer: %s", peer_key[:10])
        curr = self.peers[peer_key].score
        self.peers[peer_key].score = max(0.0, curr * 0.75)

    def reward(self, peer_key: Key):
        if peer_key == self.key:
            return
        LOGGER.debug("Rewarding peer: %s", peer_key[:10])
        curr = self.peers[peer_key].score
        self.peers[peer_key].score = min(1.0, curr * 1.075)

    def broadcast_empty_slot(self):
        msg = ConsensusMessage(type=MessageType.EMPTY_SLOT)
        self.broadcast(msg)

    def broadcast_bootstrap_request(self):
        msg = ConsensusMessage(type=MessageType.BOOTSTRAP_REQUEST)
        self.broadcast(msg)

    def recv(self):
        return self._communicator.recv()

    # Message Handlers #

    def handle_vote(self, msg: ConsensusMessage, peer_key: Key):
        # This might indicate that a node is lagging far behind or that the sender is malicious.
        if msg.epoch != self.epoch.next_epoch_number:
            return

        # Ignore rebroadcasted ballots if already handled
        if self.voting.has_voted(peer_key, msg.epoch):
            return

        LOGGER.debug(f"Received ballot for epoch {msg.epoch} from {peer_key[:5]}")

        self.voting.add_ballot(msg.epoch, peer_key, msg.votes)

        if self.broadcast_timer is not None:
            self.broadcast_timer.cancel()

        if self.voting.has_all_ballots(msg.epoch, self.online_peers):
            self.broadcast_result(msg.epoch)
        elif self.voting.has_enough_ballots(msg.epoch, self.online_peers):
            self.broadcast_timer = threading.Timer(
                15.0, self.broadcast_result, (msg.epoch,)
            )
            self.broadcast_timer.start()

    def handle_vote_result(self, msg: ConsensusMessage, peer_key: Key) -> bool:
        """
        Stores the peer result.
        Return True if receiving the result triggers a new epoch, False otherwise.
        """
        if msg.epoch != self.epoch.next_epoch_number:
            return False

        self.voting.set_peer_result(msg.epoch, peer_key, tuple(msg.result))  # type: ignore
        result, count = self.voting.get_consensus_result(msg.epoch)

        trigger_new_epoch = count >= self.voting.consensus_amount(self.online_peers) and self.epoch.number != 0
        trigger_first_epoch = count == self.online_peers and self.epoch.number == 0

        if trigger_new_epoch or trigger_first_epoch:
            self.ready_result[msg.epoch] = True
            self.voting.set_candidates(msg.epoch, result)
            if self.epoch.is_over:
                self.initialize_epoch(msg.epoch)
                return True
        return False

    def next_slot(self, block_id: str):
        try:
            self.epoch.increment_witness(block_id)
        except ZeroDivisionError:
            LOGGER.info("Failed to increment witness")
            return

        if self.epoch.is_over:
            self.finalize_epoch()

            if self.epoch.next_epoch_number in self.ready_result:
                self.initialize_epoch(self.epoch.next_epoch_number)

            else:
                LOGGER.debug(
                    "############ Result for next epoch is not ready! ###############"
                    "\nhas voted: %s\nreceived ballots: %s\nreceived results: %s\ncurrent epoch: %s",
                    self.voting.has_voted(self.key, self.epoch.next_epoch_number),  # type: ignore
                    self.voting.ballots.get(self.epoch.next_epoch_number, 0),
                    self.voting.results.get(self.epoch.next_epoch_number, 0),
                    self.epoch.number,
                )
