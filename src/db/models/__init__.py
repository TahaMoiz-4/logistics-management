"""
src/db/models/__init__.py

Exposes every model and the Base so the rest of the app only needs:

    from src.db.models import Base, Company, Depot, Vehicle, ...

Also exposes all Enums so you don't have to hunt for them separately:

    from src.db.models import OrderStatus, VehicleType, ...
"""

from src.db.models.base import Base
from src.db.models.company import Company
# from src.db.models.cost_profile import CostProfile
from src.db.models.customer import Customer
# from src.db.models.delivery_window import DeliveryWindow
from src.db.models.depot import Depot
from src.db.models.driver import Driver
from src.db.models.employee import Employee
from src.db.models.location import Location
from src.db.models.nurse import Nurse
from src.db.models.order import Order
from src.db.models.route_plan import RoutePlan
from src.db.models.driver_route import DriverRoute
from src.db.models.driver_route_stop import DriverRouteStop
from src.db.models.worker_assignment import WorkerAssignment
from src.db.models.worker_assignment_stop import WorkerAssignmentStop
from src.db.models.device_token import DeviceToken
from src.db.models.worker_position_event import WorkerPositionEvent
from src.db.models.sys_users import SysUsers
from src.db.models.technician import Technician
from src.db.models.traffic_profile import TrafficProfile
from src.db.models.user_company import UserCompany
from src.db.models.vehicle_position_event import VehiclePositionEvent
from src.db.models.vehicle import Vehicle
from src.db.models.zone import Zone


__all__ = [
    "Base",
    "Company", "Customer", "Driver", "Depot",
    "Employee", "Location", "Nurse", "Order",
    "RoutePlan", "DriverRoute", "DriverRouteStop",
    "WorkerAssignment", "WorkerAssignmentStop",
    "DeviceToken", "WorkerPositionEvent", "SysUsers",
    "Technician", "TrafficProfile", "UserCompany", "VehiclePositionEvent",
    "Vehicle", "Zone",
]