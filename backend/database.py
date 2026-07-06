"""Database engine and session management."""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://fallwatch:fallwatch_dev_password@localhost:5432/fallwatch",
)

# Force the PostgreSQL session into UTC so date()/extract() bucketing in the
# statistics endpoints matches the UTC cutoffs computed in Python, regardless
# of server or client locale.
_connect_args = ({"options": "-c timezone=utc"}
                 if DATABASE_URL.startswith("postgresql") else {})
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
