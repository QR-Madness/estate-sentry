# db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite file-based database URL
DATABASE_URL = "sqlite:///./estate-sentry.db"

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create the session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
