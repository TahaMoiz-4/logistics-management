"""
src/db/models/__init__.py

Exposes every model and the Base so the rest of the app only needs:

    from src.db.models import Base, Company, Depot, Vehicle, ...

Also exposes all Enums so you don't have to hunt for them separately:

    from src.db.models import OrderStatus, VehicleType, ...
"""

from src.db.models.base import Base
from src.db.models.company import Company
from src.db.models.cost_profile import CostProfile
from src.db.models.customer import Customer
from src.db.models.delivery_window import DeliveryWindow
from src.db.models.depot import Depot
from src.db.models.driver import Driver
from src.db.models.location import Location
from src.db.models.order import Order
from src.db.models.route_plan import RoutePlan
from src.db.models.route_stop import RouteStop
from src.db.models.route import Route
from src.db.models.traffic_profile import TrafficProfile
from src.db.models.vehicle_position_event import VehiclePositionEvent
from src.db.models.vehicle import Vehicle
from src.db.models.zone import Zone


__all__ = [
    "Base",
    "Company", "Depot", "CostProfile", "Vehicle", "Driver",
    "Customer", "Location", "Order", "DeliveryWindow",
    "Zone", "TrafficProfile", "RoutePlan", "Route",
    "RouteStop", "VehiclePositionEvent",
]