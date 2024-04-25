import logging
import random
from functools import reduce
from typing import Dict, List, Tuple

from stvpoll.scottish_stv import ScottishSTV

from .consensus_node import PeerNode
from .types import Ballot, Key, Result
from .utils import concat_and_hash

LOGGER = logging.getLogger(__name__)


class VotingSystem:
    """Creates ballots, receives ballots, and computes results"""

    def __init__(self, key: Key, peers: List[Key], slots: int):
        self.key = key
        self.peer_keys = peers
        self.polls: Dict[int, ScottishSTV] = {}
        self.ballots: Dict[int, Dict[Key, Ballot]] = {}
        self.results: Dict[int, Dict[Key, Result]] = {}
        self.candidates: Dict[int, List[Key]] = {}
        self.num_slots: int = slots

    def fill_ballot(self, peers: Dict[str, PeerNode]) -> List[Key]:
        """Fills a ballot based on the scores of peers and returns it"""
        LOGGER.debug(f"ballot peers: {peers}")

        population = self.peer_keys.copy()
        weights = [peers[p].score if peers[p].online else 0.001 for p in population]
        ballot = []

        while len(population):
            candidate = random.choices(population, weights=weights, k=1)[0]
            ballot.append(candidate)
            idx = population.index(candidate)
            population.pop(idx)
            weights.pop(idx)

        # ballot = random.sample(population, scores)
        # ballot = random.shuffle(self.peer_keys.copy())
        # ballot.sort(
        #     key=lambda k: peers[k].score if peers[k].online else 0.0, reverse=True
        # )
        return ballot

    def add_ballot(self, epoch_number: int, key: Key, ballot: Ballot):
        """
        Stores ballots by epoch and peer
        """
        if not epoch_number in self.ballots:
            self.ballots[epoch_number] = {}

        self.ballots[epoch_number][key] = ballot

    def set_candidates(self, epoch_number: int, result: Result):
        """
        Sets the candidate list for an epoch.
        """
        self.candidates[epoch_number] = list(result)

    def get_consensus_result(self, epoch_number: int) -> Tuple[Result, int]:
        """
        Returns a tuple consisting of the winning result and the count of its occurrences.
        """
        results: Dict[Result, int] = {}
        for r in self.results[epoch_number].values():
            if results.get(r):
                results[r] += 1
            else:
                results[r] = 1

        result = max(results, key=results.get)
        count = results[result]
        return (result, count)

    def calculate_result(self, epoch_number: int) -> List[Key]:
        """
        Calculates a candidate list based on received ballots for a given epoch.
        """
        self.polls[epoch_number] = ScottishSTV(
            seats=len(self.peer_keys),
            candidates=tuple(self.peer_keys),
            random_in_tiebreaks=False,
        )

        for ballot in self.ballots[epoch_number].values():
            self.polls[epoch_number].add_ballot(ballot)

        result = self.polls[epoch_number].calculate()
        result = list(map(lambda c: Key(str(c)), result.elected_as_tuple()))

        if len(result) < len(self.peer_keys):
            # Result might not have enough candidates since the STV-library does not support seeded tie-breaks
            result = break_ties(
                result,
                self.ballots[epoch_number].values(),
                len(self.peer_keys),
                epoch_number,
            )

        self.set_peer_result(epoch_number, self.key, tuple(result))
        return result

    def get_candidates(self, epoch_number: int) -> Result:
        """
        Returns candidate list for a given epoch.
        Assumes the voting is done and the result has been computed.
        """
        return self.candidates.get(epoch_number)

    def set_peer_result(self, epoch_number: int, peer_key: Key, result: Result):
        """
        Stores the voting result from a peer by epoch.
        """
        if not epoch_number in self.results:
            self.results[epoch_number] = {}

        self.results[epoch_number][peer_key] = result

    def has_voted(self, key: Key, epoch_number: int) -> bool:
        """
        Check if a peer has voted for a given epoch.
        Returns True if the node has voted, False otherwise.
        """
        if epoch_number in self.ballots:
            return key in self.ballots[epoch_number]
        return False

    def has_enough_ballots(self, epoch_number: int, online_peers: int) -> bool:
        """
        To calculate a valid result, the node has to receive ballots from at least 2/3 of
        the online peers.
        """
        required_amount = self.consensus_amount(online_peers)
        return len(self.ballots[epoch_number]) >= required_amount

    def has_all_ballots(self, epoch_number: int, online_peers: int):
        """Returns True if ballots have been received from all online peers."""
        has_minimum = online_peers >= self.consensus_amount(online_peers)
        has_all = len(self.ballots[epoch_number]) >= online_peers
        return has_minimum and has_all

    def has_enough_similar_results(self, epoch_number: int, online_peers: int) -> bool:
        """
        To be able to determine that an epoch can be started, the node needs to know that at least
        2/3 of the online peers have the same result (candidates and witnesses) for the given epoch.
        """
        if self.results[epoch_number].get(self.key) is None:
            return False

        min_results = self.consensus_amount(online_peers)
        enough_results = len(self.results[epoch_number].keys()) >= min_results

        if not enough_results:
            return False

        similar_results = 0
        own_result = self.results[epoch_number][self.key]

        similar_results = reduce(
            lambda acc, cur: acc if cur != own_result else acc + 1,
            self.results[epoch_number].values(),
            0,
        )

        return similar_results >= min_results

    def consensus_amount(self, online_peers: int):
        """2/3 of the online members have to agree for a consensus to be considered met."""
        return max(self.num_slots, 1 + ((online_peers * 2) // 3))

    def remove_old_epoch_data(self):
        """Removes data for old epochs. Keeps data for 5 last epochs."""
        if len(self.results) >= 10:
            epochs = list(self.results.keys())
            epochs.sort()
            for epoch in epochs[:-5]:
                del self.results[epoch]
                del self.candidates[epoch]
                del self.ballots[epoch]


def break_ties(
    result: Result, ballots: List[Ballot], num_candidates: int, seed: int
) -> Result:
    """
    Simple/naive tie resolution with seeded randomness. Uses a seed to randomize outcome of the
    same tie (when the same set of candidates draw for a slot) over time.
    """
    weights = [0.5]

    for i in range(1, num_candidates):
        weights.append(weights[i - 1] / 2)

    scores = {}

    for ballot in ballots:
        for i, candidate in enumerate(ballot):
            if candidate not in result:
                if candidate not in scores:
                    scores[candidate] = weights[i]
                else:
                    scores[candidate] += weights[i]

    LOGGER.debug(
        "ballots: %i\nresult: %i\nScores: %s", len(ballots), len(result), scores
    )

    for _ in range(len(result), num_candidates):
        max_score = max(scores.values())
        draws = [c for c, score in scores.items() if score == max_score]
        winner = get_slot_winner(draws, seed)
        scores.pop(winner)
        result.append(winner)

    return result


def get_slot_winner(candidates: List[Key], seed: int):
    """Chooses a single element from a list randomly using a seed."""
    if len(candidates) == 1:
        return candidates[0]
    keys_hashes = {k: concat_and_hash(k, seed) for k in candidates}
    return max(keys_hashes, key=keys_hashes.get)
