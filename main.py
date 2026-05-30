from fastapi import FastAPI, HTTPException, Depends, Query, Header
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from datetime import datetime
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import models
from database import engine, get_db

# Load environment variables
load_dotenv()
API_SECRET_KEY = os.getenv("API_SECRET_KEY")

if not API_SECRET_KEY:
    raise ValueError("API_SECRET_KEY environment variable is not set!")

app = FastAPI()

# Create the database tables if they don't exist yet
models.Base.metadata.create_all(bind=engine)

# ========== ENUM & PYDANTIC MODELS ==========
class Category(str, Enum):
    STRENGTH = "Strength"
    CARDIO = "Cardio"
    YOGA = "Yoga"

    @classmethod
    def _missing_(cls, value):
        value = value.lower()
        for member in cls:
            if member.value.lower() == value:
                return member
        return None
    
class Workout(BaseModel):
    exercise: str
    reps: int
    sets: int
    category: Category

class WorkoutUpdate(BaseModel):
    exercise: Optional[str] = None
    reps: Optional[int] = None
    sets: Optional[int] = None
    category: Optional[Category] = None
    
# ========== CREATE (POST) ==========
@app.post("/workouts", status_code=201)
def add_workout(
    workouts: List[Workout], 
    x_api_key: str = Header(None), # The security gatekeeper is now here!
    db: Session = Depends(get_db)  # Talking directly to your SQL database
):
    # 1. Block intruders
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    # 2. Save authorized data straight to SQLite
    for w in workouts:
        db_workout = models.SQLWorkout(
            exercise=w.exercise,
            reps=w.reps,
            sets=w.sets,
            category=w.category.value
        )
        db.add(db_workout)
    
    db.commit() 
    return {"message": "Authenticated and saved directly to your SQL database!"}

# ========== READ (GET) - ALL WITH FILTERS (SQL VERSION) ==========
@app.get("/workouts")
def get_workouts(
    category: Optional[Category] = Query(None, description="Filter by category"),
    min_reps: Optional[int] = Query(None, description="Minimum repetitions"),
    max_reps: Optional[int] = Query(None, description="Maximum repetitions"),
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    """Get all workouts with optional filters from the SQL database"""
    
    # 1. Start a base query pointing to your SQL table
    query = db.query(models.SQLWorkout)
    
    # 2. Add filters dynamically based on what the user types in the browser
    if category:
        query = query.filter(models.SQLWorkout.category == category.value)
    
    if min_reps is not None:
        query = query.filter(models.SQLWorkout.reps >= min_reps)
        
    if max_reps is not None:
        query = query.filter(models.SQLWorkout.reps <= max_reps)
    
    # 3. Execute the query and pull the list from workouts.db
    filtered_workouts = query.all()
    
    return {
        "total": len(filtered_workouts),
        "workouts": filtered_workouts
    }


# ========== READ (GET) - SINGLE WORKOUT (SQL VERSION) ==========
@app.get("/workouts/{workout_id}")
def get_workout_by_id(
    workout_id: int,
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    """Get a single workout by its unique SQL ID"""
    
    # Target the exact row matching the given unique ID
    workout = db.query(models.SQLWorkout).filter(models.SQLWorkout.id == workout_id).first()
    
    if workout:
        return {
            "id": workout_id,
            "workout": workout
        }
        
    raise HTTPException(
        status_code=404, 
        detail=f"Workout with id {workout_id} not found in the database"
    )

# ========== UPDATE (PUT) - MODIFY EXISTING (SQL VERSION) ==========
@app.put("/workouts/{workout_id}")
def update_workout(
    workout_id: int,
    workout_update: WorkoutUpdate,  # Still using your awesome Pydantic partial update model!
    db: Session = Depends(get_db)   # ← Real SQL Session injected here!
):
    """Update a specific workout in the SQL database (partial updates allowed)"""
    
    # 1. Look up the existing row in the database by its unique ID
    db_workout = db.query(models.SQLWorkout).filter(models.SQLWorkout.id == workout_id).first()
    
    # If the row doesn't exist, immediately throw a 404
    if not db_workout:
        raise HTTPException(
            status_code=404,
            detail=f"Workout with id {workout_id} not found"
        )
    
    # 2. Update only the fields that the user actually provided in the request
    if workout_update.exercise is not None:
        db_workout.exercise = workout_update.exercise
    
    if workout_update.reps is not None:
        if workout_update.reps <= 0:
            raise HTTPException(status_code=400, detail="Reps must be positive")
        db_workout.reps = workout_update.reps
    
    if workout_update.sets is not None:
        if workout_update.sets <= 0:
            raise HTTPException(status_code=400, detail="Sets must be positive")
        db_workout.sets = workout_update.sets
    
    if workout_update.category is not None:
        db_workout.category = workout_update.category.value
    
    # 3. Save the changes permanently to workouts.db
    db.commit()
    
    # 4. Refresh our local object to capture any DB-side changes (like timestamps)
    db.refresh(db_workout)
    
    return {
        "message": f"Workout {workout_id} updated successfully in the SQL database!",
        "updated_workout": db_workout
    }

# ========== DELETE - SINGLE WORKOUT (SQL VERSION) ==========
@app.delete("/workouts/{workout_id}")
def delete_single_workout(
    workout_id: int,
    x_api_key: str = Header(None),  # ← Security Gatekeeper added here!
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    """Securely delete a single workout by its ID"""
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    # 1. Target the specific row matching the given unique ID
    db_workout = db.query(models.SQLWorkout).filter(models.SQLWorkout.id == workout_id).first()
    
    # If the row doesn't exist, throw a 404
    if not db_workout:
        raise HTTPException(
            status_code=404,
            detail=f"Workout with id {workout_id} not found"
        )
    
    # 2. Delete the row and save the changes permanently to workouts.db
    db.delete(db_workout)
    db.commit()
    
    return {
        "message": f"Workout {workout_id} deleted successfully from the SQL database"
    }


# ========== DELETE - MULTIPLE WORKOUTS (SQL VERSION) ==========
@app.delete("/workouts")
def delete_multiple_workouts(
    workout_ids: List[int],
    x_api_key: str = Header(None),  # ← Security Gatekeeper added here!
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    
    """Securely delete multiple workouts by their ID"""
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    # 1. Find all rows where the ID matches any number inside the workout_ids list
    # The .in_() operator acts like a clean SQL query: WHERE id IN (1, 2, 3)
    query = db.query(models.SQLWorkout).filter(models.SQLWorkout.id.in_(workout_ids))
    
    # Fetch the actual matching items so we know how many we found
    matching_workouts = query.all()
    deleted_count = len(matching_workouts)
    
    if deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="None of the provided IDs were found in the database"
        )
    
    # 2. Delete all targeted rows simultaneously and save to disk
    query.delete(synchronize_session=False)
    db.commit()
    
    return {
        "message": f"Deleted {deleted_count} workouts successfully from the SQL database",
        "requested_ids": workout_ids
    }

# ========== STATISTICS - SUMMARY (SQL VERSION) ==========
@app.get("/workouts/stats/summary")
def get_workout_statistics(
    x_api_key: str = Header(None),  # ← Security Gatekeeper added here!
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    
    """Securely view comprehensive statistics about all workouts"""
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    """Get comprehensive statistics about all workouts from the SQL database"""
    
    # 1. Fetch all workout records out of the SQL table
    all_workouts = db.query(models.SQLWorkout).all()
    
    # If the database table is completely empty, return an empty structure
    if not all_workouts:
        return {
            "total_workouts": 0,
            "message": "No workouts found. Add some workouts first!"
        }
    
    # Initialize your stats dictionary (keeping your exact original structure!)
    stats = {
        "total_workouts": len(all_workouts),
        "total_reps": 0,
        "total_sets": 0,
        "average_reps_per_workout": 0,
        "average_sets_per_workout": 0,
        "by_category": {},
        "most_common_exercise": None,
        "exercise_counts": {}
    }
    
    # 2. Calculate totals using the records pulled from SQL
    exercise_count = {}
    for workout in all_workouts:
        stats["total_reps"] += workout.reps     # Note: Using dot notation (workout.reps)
        stats["total_sets"] += workout.sets     # instead of dictionary brackets now!
        
        # Count by category
        category = workout.category
        if category not in stats["by_category"]:
            stats["by_category"][category] = {
                "count": 0,
                "total_reps": 0,
                "total_sets": 0
            }
        stats["by_category"][category]["count"] += 1
        stats["by_category"][category]["total_reps"] += workout.reps
        stats["by_category"][category]["total_sets"] += workout.sets
        
        # Count exercises
        exercise = workout.exercise
        exercise_count[exercise] = exercise_count.get(exercise, 0) + 1
    
    # Calculate averages
    stats["average_reps_per_workout"] = round(stats["total_reps"] / len(all_workouts), 2)
    stats["average_sets_per_workout"] = round(stats["total_sets"] / len(all_workouts), 2)
    
    # Find most common exercise
    if exercise_count:
        stats["most_common_exercise"] = max(exercise_count, key=exercise_count.get)
        stats["exercise_counts"] = exercise_count
    
    return stats

# ========== STATISTICS - BY CATEGORY (SQL VERSION) ==========
@app.get("/workouts/stats/category/{category_name}")
def get_category_stats(
    category_name: Category,
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    """Get statistics for a specific category from the SQL database"""
    
    # 1. Ask the database to filter rows matching the category name
    # This runs: SELECT * FROM workouts WHERE category = :category_name;
    category_workouts = db.query(models.SQLWorkout).filter(
        models.SQLWorkout.category == category_name.value
    ).all()
    
    # If no rows come back from the database for this category
    if not category_workouts:
        return {
            "category": category_name.value,
            "count": 0,
            "message": f"No workouts found in {category_name.value} category"
        }
    
    # 2. Calculate totals using dot notation (.reps and .sets) on the SQL objects
    total_reps = sum(w.reps for w in category_workouts)
    total_sets = sum(w.sets for w in category_workouts)
    
    return {
        "category": category_name.value,
        "count": len(category_workouts),
        "total_reps": total_reps,
        "total_sets": total_sets,
        "average_reps": round(total_reps / len(category_workouts), 2),
        "average_sets": round(total_sets / len(category_workouts), 2),
        "workouts": category_workouts
    }
    
    #==========Authentication: ==================
    # I am using API Key Authentication
    
    # Load environment variables
load_dotenv()
API_SECRET_KEY = os.getenv("API_SECRET_KEY")

# DEBUG - Add these lines
print(f"=== DEBUG ===")
print(f"API_SECRET_KEY value: '{API_SECRET_KEY}'")
print(f"Type: {type(API_SECRET_KEY)}")
print(f"Length: {len(API_SECRET_KEY) if API_SECRET_KEY else 0}")
print(f"==============")
    # Define a "Master Key" (In real life, this is hidden)
#API_SECRET_KEY = os.getenv("API_SECRET_KEY")

if not API_SECRET_KEY:
    raise ValueError("API_SECRET_KEY environment variable is not set!")

# ========== CREATE (POST) - SECURE & SQL CONNECTED ==========
@app.post("/workouts", status_code=201)
def add_workout(
    workouts: List[Workout],       # Your Pydantic model validating incoming data
    x_api_key: str = Header(None), # The security gatekeeper looking for X-API-Key in headers
    db: Session = Depends(get_db)  # ← Real SQL Session injected here!
):
    """Securely add workouts directly into the SQL database using an API key"""
    
    # 1. The Security Gatekeeper
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    # 2. Convert and save authorized data straight to SQLite
    for w in workouts:
        db_workout = models.SQLWorkout(
            exercise=w.exercise,
            reps=w.reps,
            sets=w.sets,
            category=w.category.value
        )
        db.add(db_workout) # Stage it in the database session
    
    db.commit() # Save changes permanently to your workouts.db file!
    
    return {"message": "Authenticated and saved directly to your SQL database!"}