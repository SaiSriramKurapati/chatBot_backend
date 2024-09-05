from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import yaml
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
# Initializing Environmental Variables
# load_dotenv(dotenv_path="backend/.env")
SQLALCHEMY_DATABASE_URL = os.getenv("MY_DATABASE_URL")

# === Create SQLAlchemy Engine ===
# The engine is the core interface to the database in SQLAlchemy.
# It is responsible for establishing and managing connections to the database.
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# === Create a Configured "Session" Class ===
# The sessionmaker factory function is used to create a session class.
# Sessions are used to interact with the database (e.g., querying, adding, deleting data).
# The session is configured not to autocommit transactions automatically and not to autoflush changes.
# The session is bound to the engine, meaning it uses the engine for database operations.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# === Create a Base Class for the ORM Models ===
# The declarative_base function returns a base class that all ORM models will inherit from.
# This base class is used by SQLAlchemy to know which classes are mapped to database tables.
Base = declarative_base()

# === Database Dependency ===
# This function is a dependency that can be used in FastAPI routes to get a database session.
# When called, it provides a session that can be used to interact with the database.
# The session is closed automatically once the operation is complete.
def get_db():
    # Creates a new session from the SessionLocal factory.
    db = SessionLocal()
    try:
        # Yield the session to the caller.
        yield db
    finally:
        # Close the session to free up resources.
        db.close()
