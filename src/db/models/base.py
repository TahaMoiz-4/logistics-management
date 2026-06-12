from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

def gen_uuid():
    return str(uuid.uuid4())
