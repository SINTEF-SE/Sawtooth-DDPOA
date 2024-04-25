from functools import reduce
from hashlib import sha256


def concat_and_hash(*args) -> str:
    """Concats arguments to a single string and hashes it. Returns the hexdigest (a string)."""
    src: str = reduce(lambda x, y: x + str(y), args, "")
    return sha256(src.encode()).hexdigest()

def try_remove(l, i):
    try:
        l.remove(i)
    except:
        pass