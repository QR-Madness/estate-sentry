from sqlalchemy import Column, Integer, String, JSON

from .base import Base


class Sensor(Base):
    __tablename__ = 'sensors'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    handler = Column(String, nullable=True)
    public_key = Column(String, nullable=True)
    connection_type = Column(String, nullable=True)
    connection_details = Column(JSON, nullable=False, default={})
    metadata = Column(JSON, nullable=True)
