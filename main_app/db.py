from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Generator
import os
from dotenv import load_dotenv
from .logging_config import get_logger, log_error

load_dotenv()
logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Ajay.kumar0518@db.suczkghtbhntlhclrcmv.supabase.co:5432/postgres")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Database dependency with connection logging"""
    db = None
    try:
        db = SessionLocal()
        logger.debug("Database session created")
        yield db
    except SQLAlchemyError as e:
        if db:
            db.rollback()
        log_error(logger, e, {}, "database_session_error")
        raise
    except Exception as e:
        if db:
            db.rollback()
        log_error(logger, e, {}, "database_unexpected_error")
        raise
    finally:
        if db:
            db.close()
            logger.debug("Database session closed")