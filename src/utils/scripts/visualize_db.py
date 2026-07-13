from sqlalchemy_data_model_visualizer import generate_data_model_diagram
from src.db.models import Company, Customer, Depot, Driver, Nurse, UserCompany, SysUsers, Technician, Employee, Vehicle, DriverRoute, DriverRouteStop, WorkerAssignment, WorkerAssignmentStop, Order, RoutePlan, TrafficProfile, VehiclePositionEvent, Location, Zone
from datetime import date

models = [
    Company, Customer, Driver, Depot,
    Employee, Location, Nurse, Order,
    RoutePlan, DriverRoute, DriverRouteStop, WorkerAssignment, WorkerAssignmentStop, SysUsers,
    Technician, TrafficProfile, UserCompany, VehiclePositionEvent,
    Vehicle, Zone]

generate_data_model_diagram(models, output_file=fr'documentation\ERDs\db__erd_{date.today()}')