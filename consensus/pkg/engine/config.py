# How many times the same witness list is used before starting a new vote
ROUNDS_PER_EPOCH = 3

# Seconds between block creation (aka the size of a slot)
BLOCK_INTERVAL = 6

# Time after expecting a block before the slot is considered missed (should be quite long since the validator is slow sometimes)
SLOT_TIMEOUT = 90

# Votes are rebroadcasted until enough votes are received in case a
# node was down or had network issues
REBROADCAST_BALLOT_INTERVAL = 5

# How often the it is checked how long it has been since the peer nodes have been seen
PEER_CHECK_INTERVAL = 3

# How long it has to be since a node was seen before sending a ping
PING_THRESHOLD = 30

GENESIS_BLOCK_ID = b"\x00\x00\x00\x00\x00\x00\x00\x00"

# How many slots before the end of an epoch the voting for the next epoch should start
VOTING_SLOTS = 5
