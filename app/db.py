import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DB_URL = os.getenv("DB_URL", "sqlite:///./trustipay.db")

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Ensure schema exists and verify connectivity."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))


def check_db_connection() -> bool:
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_existing_tables() -> list[str]:
    return sorted(inspect(engine).get_table_names())
