"""
Estate Sentry database module.
"""

from .session import engine
import logging
from .models.base import Base


def initialize_database():
    logging.info("Init database...")
    Base.metadata.create_all(bind=engine)