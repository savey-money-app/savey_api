from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import event
from .config import settings


Base = declarative_base()

# Create a single global engine with proper connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,              # Maximum 10 persistent connections
    max_overflow=20,           # Allow 20 additional connections during peak
    pool_timeout=30,           # Wait 30s for connection before failing
    pool_recycle=3600,         # Recycle connections after 1 hour
    pool_pre_ping=True,        # Verify connections are alive before using
    echo=False,                # Set to True for SQL debugging
)

# Set search_path to 'savey' schema for all connections
@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """Set search_path to 'savey' schema on every new connection"""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO savey")
    cursor.close()

# Create a global session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get a database session. Use in FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.commit()
        db.close()

