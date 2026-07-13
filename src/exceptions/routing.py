class NoRouteFound(Exception):
    pass


class LocationUnroutable(Exception):
    """
    A location can't be routed on the road graph — it's off the serviceable
    (Karachi) map or no path exists to/from it. This is a DATA problem: the
    solve hard-fails so the bad location is surfaced rather than silently
    straight-lined into a schedule. (Distinct from a whole-graph infra failure,
    which falls back to Haversine.)
    """
    def __init__(self, lat: float, lng: float, detail: str = ""):
        self.lat = lat
        self.lng = lng
        self.detail = detail
        super().__init__(
            f"Location ({lat}, {lng}) is unroutable on the road network"
            + (f": {detail}" if detail else ".")
        )