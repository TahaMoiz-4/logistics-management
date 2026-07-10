from sqlalchemy_data_model_visualizer import generate_data_model_diagram
from src.db.models import Company, Customer, Depot, Driver, Vehicle, Route, DeliveryWindow, CostProfile, Order, RoutePlan, RouteStop, TrafficProfile, VehiclePositionEvent, Location, Zone 

models = [Company, Customer, Depot, Driver, Vehicle, Route, DeliveryWindow, CostProfile, Order, RoutePlan, RouteStop, TrafficProfile, VehiclePositionEvent, Location, Zone] 
generate_data_model_diagram(models, output_file='my_database_erd')