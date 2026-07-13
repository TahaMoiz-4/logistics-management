"""src/db/repositories/depot.py"""

from src.db.models import Depot
from src.db.repositories.base import BaseRepository


class DepotRepository(BaseRepository[Depot]):
    model = Depot
