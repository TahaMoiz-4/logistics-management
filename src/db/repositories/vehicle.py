"""src/db/repositories/vehicle.py"""

from src.db.models import Vehicle
from src.db.repositories.base import BaseRepository


class VehicleRepository(BaseRepository[Vehicle]):
    model = Vehicle
