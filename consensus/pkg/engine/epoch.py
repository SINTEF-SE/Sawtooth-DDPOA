import logging
from queue import Queue
from typing import List

from .config import ROUNDS_PER_EPOCH
from .types import Key
from .utils import concat_and_hash

LOGGER = logging.getLogger(__name__)


class Epoch:
    """
    Holds witness list and keeps control over slots
    and epoch state (current/next/all witnesses).
    """

    def __init__(self, number: int, slots: int):
        self.number: int = number
        self.current_witness_idx: int = 0
        self.candidates: Queue = Queue()
        self.witnesses: List[Key] = []
        self.num_slots = slots

    def set_candidates_and_witnesses(self, candidates: List[Key]):
        """
        Puts top self.num_slots (as defined from on-chain setting) candidates in the witness list and the rest
        in the candidate queue.
        """

        self.witnesses = candidates[: self.num_slots]
        for candidate in candidates[self.num_slots :]:
            self.candidates.put(candidate)

    def increment_witness(self, pre_block_id: str):
        """
        Tells epoch to proceed to next slot in the witness list.
        Witness list is reordered if slot increase leads to round increase.
        """
        self.current_witness_idx = self.current_witness_idx + 1
        try:
            if self.current_witness_idx % len(self.witnesses) == 0 and not self.is_over:
                self.reorder_witnesslist(pre_block_id)
        except ZeroDivisionError:
            LOGGER.error(
                "For pre_block id: %s {} with epoch info: %s {str(self)}",
                pre_block_id,
                self,
            )
            raise ZeroDivisionError  # Need to catch up somehow

    def downgrade_witness(self, witness_key: Key):
        """
        Replaces a witness with one from the candidates list (if the provided key belongs
        to a witness). The replaced witness is placed at the back of the candidates queue.
        """
        if not self.is_witness(witness_key):
            return

        downgraded_idx = self.witnesses.index(witness_key)
        upgraded_candidate = self.candidates.get()
        self.candidates.put(witness_key)
        self.witnesses[downgraded_idx] = upgraded_candidate

    def is_witness(self, node_key: Key):
        """Returns True if node is a witness the in epoch."""
        return node_key in self.witnesses

    def position_in_witness_list(self, node_key: Key):
        """
        Returns index in witness list if the node is in it.
        If the node is not a witness, None is returned.
        """
        try:
            return self.witnesses.index(node_key)
        except ValueError:
            return None

    def reorder_witnesslist(self, seed):
        """
        Reorders the witnesslist based on a seed and witness idx (so it is reordered even if the same
        seed is used again, which happens if block_id is the seed and no new block has been produced).
        Used to make it difficult to predict block producers further ahead than in the current round of the epoch.
        """
        hashes = [
            (w, concat_and_hash(w, seed, self.current_witness_idx))
            for w in self.witnesses
        ]
        hashes.sort(key=lambda h: h[1])
        witnesslist = list(map(lambda h: h[0], hashes))
        self.witnesses = witnesslist

    @property
    def current_witness(self) -> Key:
        """
        Returns the key of the current witness or None if there
        is no current witness (the epoch is over or not started).
        """
        if not self.witnesses:
            return None
        idx = self.current_witness_idx % len(self.witnesses)
        try:
            return self.witnesses[idx]
        except IndexError:
            return None

    @property
    def next_witness(self) -> Key:
        """
        Returns the key of the next witness or None if there
        is no next witness (the epoch is soon over or not started).
        """
        if not self.witnesses:
            LOGGER.debug("No witnesses in epoch: %s", self)
            return None
        idx = (self.current_witness_idx + 1) % len(self.witnesses)
        try:
            return self.witnesses[idx]
        except IndexError:
            LOGGER.debug("Witness %s not found in epoch: %s", idx, self)
            return None

    @property
    def is_initialized(self) -> bool:
        """
        Returns True if the epoch has been initialized.
        """
        return not (self.current_witness_idx == 0 and len(self.witnesses) == 0)

    @property
    def is_over(self) -> bool:
        """
        Returns True if the last iteration of the witness list is done,
        indicating that the epoch is over.
        """
        return self.current_witness_idx >= (len(self.witnesses) * ROUNDS_PER_EPOCH)

    @property
    def next_epoch_number(self) -> int:
        """
        Returns the number of the next epoch.
        """
        return self.number + 1

    @property
    def is_last_round(self) -> bool:
        """
        Returns True if the current round is the last one in the epoch.
        """
        return self.current_witness_idx >= (
            len(self.witnesses) * (ROUNDS_PER_EPOCH - 1)
        )

    @property
    def slots_remaining_in_epoch(self) -> int:
        """
        Returns the number of slots remaining in the epoch.
        """
        return len(self.witnesses) * ROUNDS_PER_EPOCH - (self.current_witness_idx)

    @property
    def full_candidate_list(self) -> List[Key]:
        """Returns witness list concatenated with candidate list (used to bootsrap other nodes)."""
        return list(self.witnesses) + list(self.candidates.queue)

    def __str__(self):
        return (
            "Epoch("
            + ", ".join(
                [
                    "Number: {}".format(self.number),
                    "Current witness idx: {}".format(self.current_witness_idx),
                    "Candidates: {}".format(self.candidates),
                    "WItnesses: {}".format(self.witnesses),
                ]
            )
            + ")"
        )
