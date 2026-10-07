from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database URL (stored in a single file inside this folder)
SQLALCHEMY_DATABASE_URL = "sqlite:///./swiftwave.db"

# connect_args={"check_same_thread": False} is required for SQLite with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Each session instance will be a database conversation
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our database models
Base = declarative_base()

def get_db():
    """Dependency helper to safely open and close DB sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()