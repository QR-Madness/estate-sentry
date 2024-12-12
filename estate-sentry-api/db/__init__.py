from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models.base import Base

DEFAULT_DATABASE_URL = "sqlite:///estate-sentry.db"
DEFAULT_TESTING_DATABASE_URL = "sqlite:///:memory:"

# Define the engine and session globally
engine = create_engine(DEFAULT_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    **TEST DB NOT OPERATIONAL YET**

    Initialize the database with the provided URL and create all tables.
    """
    # TODO FIXME default URL keeps being used (see other method in this file and continue working on it)
    if current_app:
        with current_app.app_context():
            if current_app.config["TEST_MODE"]:
                database_url = DEFAULT_TESTING_DATABASE_URL
            else:
                database_url = DEFAULT_DATABASE_URL
    global engine, SessionLocal
    # recreate engine if initializing a new database URL
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # create tables if needed
    Base.metadata.create_all(bind=engine)

    return engine, SessionLocal


def init_test_db():
    # TODO
    pass
