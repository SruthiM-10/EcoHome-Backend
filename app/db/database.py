#app/db/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv
from contextlib import contextmanager

# load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', '.env'))


DATABASE_URL = os.getenv("DATABASE_URL")
print("Database URL:", DATABASE_URL)


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind= engine, autocommit= False, autoflush=False)

Base= declarative_base()


from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db= SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_context = contextmanager(get_db)