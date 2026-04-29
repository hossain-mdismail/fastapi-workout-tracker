from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
import json
import os

app = FastAPI()

DB_FILE = "workouts_db.json"

# ========== DATABASE FUNCTIONS ==========
def load_db():
    """Load data from file when server starts"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return []

def save_db(data):
    """Save data to file whenever we change it"""
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ========== DEPENDENCY INJECTION ==========
def get_db():
    """
    Dependency that provides the current database.
    FastAPI will call this function and inject the result.
    """
    return load_db()

def save_db_dependency(data):
    """
    Helper to save database (not a dependency, just a utility)
    """
    save_db(data)

# ========== HOME ENDPOINT ==========
@app.get("/")
def home():
    return {"status": "Fitness API is running", "user": "Ismail"}

# ========== ENUM & PYDANTIC MODELS ==========
class Category(str, Enum):
    STRENGTH = "Strength"
    CARDIO = "Cardio"
    YOGA = "Yoga"

    @classmethod
    def _missing_(cls, value):
        # Allow case-insensitive matching
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

# NEW MODEL: For partial updates (all fields optional)
class WorkoutUpdate(BaseModel):
    exercise: Optional[str] = None
    reps: Optional[int] = None
    sets: Optional[int] = None
    category: Optional[Category] = None
    
# ========== CREATE (POST) ==========
@app.post("/workouts", status_code=201)
def add_workout(
    workouts: List[Workout],
    db: List = Depends(get_db)  # ← Database injected here
):
    """Add new workouts - database is injected"""
    for w in workouts:
        db.append(w.dict())
    
    save_db(db)  # Save the modified database
    return {"message": f"{len(workouts)} workouts added!", "total": len(db)}

# ========== READ (GET) - ALL WITH FILTERS ==========
@app.get("/workouts")
def get_workouts(
    category: Optional[Category] = Query(None, description="Filter by category"),
    min_reps: Optional[int] = Query(None, description="Minimum repetitions"),
    max_reps: Optional[int] = Query(None, description="Maximum repetitions"),
    db: List = Depends(get_db)  # ← Database injected here
):
    """Get all workouts with optional filters - database is injected"""
    filtered_db = db
    
    # Filter by category
    if category:
        filtered_db = [w for w in filtered_db if w["category"] == category.value]
    
    # Filter by min reps
    if min_reps is not None:
        filtered_db = [w for w in filtered_db if w["reps"] >= min_reps]
    
    # Filter by max reps
    if max_reps is not None:
        filtered_db = [w for w in filtered_db if w["reps"] <= max_reps]
    
    return {
        "total": len(filtered_db),
        "workouts": filtered_db
    }

# ========== READ (GET) - SINGLE WORKOUT ==========
@app.get("/workouts/{workout_id}")
def get_workout_by_id(
    workout_id: int,
    db: List = Depends(get_db)  # ← Database injected here
):
    """Get a single workout by its ID/index - database is injected"""
    if 0 <= workout_id < len(db):
        return {
            "id": workout_id,
            "workout": db[workout_id]
        }
    raise HTTPException(
        status_code=404, 
        detail=f"Workout with id {workout_id} not found"
    )

# ========== UPDATE (PUT) - MODIFY EXISTING ==========
@app.put("/workouts/{workout_id}")
def update_workout(
    workout_id: int,
    workout_update: WorkoutUpdate,
    db: List = Depends(get_db)  # ← Database injected here
):
    """Update a specific workout (partial updates allowed) - database is injected"""
    
    # Check if workout exists
    if workout_id < 0 or workout_id >= len(db):
        raise HTTPException(
            status_code=404,
            detail=f"Workout with id {workout_id} not found"
        )
    
    # Get current workout
    current_workout = db[workout_id]
    
    # Update only the fields that were provided
    if workout_update.exercise is not None:
        current_workout["exercise"] = workout_update.exercise
    
    if workout_update.reps is not None:
        if workout_update.reps <= 0:
            raise HTTPException(status_code=400, detail="Reps must be positive")
        current_workout["reps"] = workout_update.reps
    
    if workout_update.sets is not None:
        if workout_update.sets <= 0:
            raise HTTPException(status_code=400, detail="Sets must be positive")
        current_workout["sets"] = workout_update.sets
    
    if workout_update.category is not None:
        current_workout["category"] = workout_update.category.value
    
    # Save to database
    db[workout_id] = current_workout
    save_db(db)  # Save the changes
    
    return {
        "message": f"Workout {workout_id} updated successfully",
        "updated_workout": current_workout
    }

# ========== DELETE - SINGLE WORKOUT ==========
@app.delete("/workouts/{workout_id}")
def delete_single_workout(
    workout_id: int,
    db: List = Depends(get_db)  # ← Database injected here
):
    """Delete a single workout by ID - database is injected"""
    
    if 0 <= workout_id < len(db):
        deleted_workout = db.pop(workout_id)
        save_db(db)  # Save the changes
        return {
            "message": f"Workout {workout_id} deleted successfully",
            "deleted_workout": deleted_workout,
            "remaining": len(db)
        }
    
    raise HTTPException(
        status_code=404,
        detail=f"Workout with id {workout_id} not found"
    )

# ========== DELETE - MULTIPLE WORKOUTS ==========
@app.delete("/workouts")
def delete_multiple_workouts(
    workout_ids: List[int],
    db: List = Depends(get_db)  # ← Database injected here
):
    """Delete multiple workouts by IDs - database is injected"""
    
    # Sort in reverse to delete from end to start (so indexes don't shift)
    workout_ids.sort(reverse=True)
    deleted_count = 0
    deleted_ids = []
    
    for wid in workout_ids:
        if 0 <= wid < len(db):
            db.pop(wid)
            deleted_count += 1
            deleted_ids.append(wid)
    
    save_db(db)  # Save changes to disk
    return {
        "message": f"Deleted {deleted_count} workouts successfully", 
        "deleted_ids": deleted_ids,
        "remaining": len(db)
    }

# ========== STATISTICS - SUMMARY ==========
@app.get("/workouts/stats/summary")
def get_workout_statistics(
    db: List = Depends(get_db)  # ← Database injected here
):
    """Get comprehensive statistics about all workouts - database is injected"""
    if not db:
        return {
            "total_workouts": 0,
            "message": "No workouts found. Add some workouts first!"
        }
    
    # Initialize stats
    stats = {
        "total_workouts": len(db),
        "total_reps": 0,
        "total_sets": 0,
        "average_reps_per_workout": 0,
        "average_sets_per_workout": 0,
        "by_category": {},
        "most_common_exercise": None,
        "exercise_counts": {}
    }
    
    # Calculate totals
    exercise_count = {}
    for workout in db:
        stats["total_reps"] += workout["reps"]
        stats["total_sets"] += workout["sets"]
        
        # Count by category
        category = workout["category"]
        if category not in stats["by_category"]:
            stats["by_category"][category] = {
                "count": 0,
                "total_reps": 0,
                "total_sets": 0
            }
        stats["by_category"][category]["count"] += 1
        stats["by_category"][category]["total_reps"] += workout["reps"]
        stats["by_category"][category]["total_sets"] += workout["sets"]
        
        # Count exercises
        exercise = workout["exercise"]
        exercise_count[exercise] = exercise_count.get(exercise, 0) + 1
    
    # Calculate averages
    stats["average_reps_per_workout"] = round(stats["total_reps"] / len(db), 2)
    stats["average_sets_per_workout"] = round(stats["total_sets"] / len(db), 2)
    
    # Find most common exercise
    if exercise_count:
        stats["most_common_exercise"] = max(exercise_count, key=exercise_count.get)
        stats["exercise_counts"] = exercise_count
    
    return stats

# ========== STATISTICS - BY CATEGORY ==========
@app.get("/workouts/stats/category/{category_name}")
def get_category_stats(
    category_name: Category,
    db: List = Depends(get_db)  # ← Database injected here
):
    """Get statistics for a specific category - database is injected"""
    category_workouts = [w for w in db if w["category"] == category_name.value]
    
    if not category_workouts:
        return {
            "category": category_name.value,
            "count": 0,
            "message": f"No workouts found in {category_name.value} category"
        }
    
    total_reps = sum(w["reps"] for w in category_workouts)
    total_sets = sum(w["sets"] for w in category_workouts)
    
    return {
        "category": category_name.value,
        "count": len(category_workouts),
        "total_reps": total_reps,
        "total_sets": total_sets,
        "average_reps": round(total_reps / len(category_workouts), 2),
        "average_sets": round(total_sets / len(category_workouts), 2),
        "workouts": category_workouts
    }