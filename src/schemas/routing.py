from dataclasses import dataclass

@dataclass
class RouteResult:
    origin_lat:       float
    origin_lng:       float
    dest_lat:         float
    dest_lng:         float
    distance_m:       int
    travel_time_sec:  int
    geometry:         dict
    multiplier_used:  float 