from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy import text
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

# Create a global session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get a database session. Use in FastAPI dependencies."""
    db = SessionLocal()
    try:
        # Set search_path inside the transaction so PgBouncer (Neon pooler)
        # keeps the same backend connection for this entire unit of work.
        db.execute(text("SET search_path TO savey"))
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
