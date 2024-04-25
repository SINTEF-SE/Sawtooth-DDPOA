from typing import List, NewType, Tuple

Key = NewType("Key", str)

Ballot = NewType("Ballot", List[str])
Result = NewType("Result", Tuple[str])
