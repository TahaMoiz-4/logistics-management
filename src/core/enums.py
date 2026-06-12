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
 
 
class RouteStatus(str, enum.Enum):
    pending   = "pending"
    active    = "active"
    completed = "completed"
    cancelled = "cancelled"
 
 
class StopType(str, enum.Enum):
    depot_start = "depot_start"
    delivery    = "delivery"
    pickup      = "pickup"
    depot_end   = "depot_end"
 
 
class PositionSource(str, enum.Enum):
    gps       = "gps"
    simulated = "simulated"
    manual    = "manual"
