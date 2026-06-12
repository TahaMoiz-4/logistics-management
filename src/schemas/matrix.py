from dataclasses import dataclass, field
from typing import List

@dataclass
class Location:
    """A single stop in the matrix — depot or delivery point."""
    lat:   float
    lng:   float
    label: str = ""              # human label for logging


@dataclass
class MatrixResult:
    """
    Output of build_matrix().

    matrix[i][j]  = travel_time_sec from location i to j
    locations     = the input list in the same order (index 0 = depot)
    multiplier    = traffic multiplier applied to the whole matrix
    cache_hits    = how many pairs were served from Redis
    computed      = how many pairs were freshly computed
    failed        = how many pairs returned PENALTY (no route found)
    """
    matrix:     List[List[int]]
    locations:  List[Location]
    multiplier: float
    cache_hits: int = 0
    computed:   int = 0
    failed:     int = 0

    @property
    def size(self) -> int:
        return len(self.locations)

    def travel_time(self, from_idx: int, to_idx: int) -> int:
        return self.matrix[from_idx][to_idx]

    def summary(self) -> str:
        total = self.size * self.size
        return (
            f"Matrix {self.size}×{self.size} ({total} pairs) | "
            f"multiplier={self.multiplier:.2f} | "
            f"cache_hits={self.cache_hits} computed={self.computed} "
            f"failed={self.failed}"
        )