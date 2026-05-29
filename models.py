from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime

class SQLWorkout(Base):
    __tablename__ = "workouts"  # This will be the name of the table inside workouts.db

    id = Column(Integer, primary_key=True, index=True)  # Auto-incrementing unique ID (1, 2, 3...)
    exercise = Column(String, index=True)
    reps = Column(Integer)
    sets = Column(Integer)
    category = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow) # Automatically tags when saved