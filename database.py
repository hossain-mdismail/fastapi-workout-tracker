from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Tell SQLAlchemy where to create the database file
DATABASE_URL = "sqlite:///./workouts.db"

# 2. Create the engine that talks to the database file
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 3. Create a Session factory (this manages database connections)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. This is the base class that our database tables will inherit from
Base = declarative_base()

# 5. Dependency helper to get a database connection for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()