import enum

class VehicleType(str, enum.Enum):
    bike   = "bike"
    car    = "car"
    van    = "van"
    truck  = "truck"
 
 
class FuelType(str, enum.Enum):
    petrol   = "petrol"
    diesel   = "diesel"
    electric = "electric"
    cng      = "cng"
 
 
class OrderPriority(str, enum.Enum):
    low    = "low"
    normal = "normal"
    high   = "high"
    urgent = "urgent"
 
 
class OrderStatus(str, enum.Enum):
    pending    = "pending"
    assigned   = "assigned"
    in_transit = "in_transit"
    delivered  = "delivered"
    failed     = "failed"
 
 
class DayType(str, enum.Enum):
    weekday          = "weekday"
    friday           = "friday"
    saturday         = "saturday"
    sunday           = "sunday"
    public_holiday   = "public_holiday"
 
 
class TrafficSource(str, enum.Enum):
    synthetic = "synthetic"
    learned   = "learned"
 
 
class PlanStatus(str, enum.Enum):
    draft       = "draft"
    optimizing  = "optimizing"
    ready       = "ready"
    dispatched  = "dispatched"
    completed   = "completed"
    failed      = "failed"
 
 
class RouteStatus(str, enum.Enum):
    pending   = "pending"
    active    = "active"
    completed = "completed"
    cancelled = "cancelled"
 
 
class StopType(str, enum.Enum):
    depot_start = "depot_start"
    delivery    = "delivery"
    dropoff     = "dropoff"       # driver drops a worker off to begin service
    pickup      = "pickup"        # driver picks a worker up after service
    depot_end   = "depot_end"
 
 
class PositionSource(str, enum.Enum):
    gps       = "gps"
    simulated = "simulated"
    manual    = "manual"

class WorkerStopStatus(str, enum.Enum):
    """Per-order execution state a field worker reports on a WorkerAssignmentStop."""
    pending     = "pending"
    en_route    = "en_route"
    arrived     = "arrived"
    in_progress = "in_progress"
    completed   = "completed"
    failed      = "failed"

class DevicePlatform(str, enum.Enum):
    android = "android"
    ios     = "ios"

class OperationalStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    inactive = "inactive"

class LocationTypes(str, enum.Enum):
    company_head_office = "company_head_office"
    company_depot = "company_depot"
    customer_location = "customer_location"

class ServiceType(str, enum.Enum):
    nurse      = "nurse"
    technician = "technician"

class TechnicianSkills(str, enum.Enum):
    network_setup = "network_setup"
    hardware_installation = "hardware_installation"
    cable_management = "cable_management"
    system_configuration = "system_configuration"

class NurseClinicalSkill(str, enum.Enum):
    iv_administration     = "iv_administration"
    phlebotomy            = "phlebotomy"
    wound_care            = "wound_care"
    triage                = "triage"
    ventilator_management = "ventilator_management"
    dialysis              = "dialysis"