"""FastAPI Backend - Study Planner API."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_db
from pipeline import StudyPlannerPipeline

# Initialize FastAPI
app = FastAPI(
    title="Study Planner API",
    description="AI-powered weekly study planner API",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class GeneratePlanRequest(BaseModel):
    """Request to generate a new study plan."""
    skip_embeddings: bool = True


class TaskUpdateRequest(BaseModel):
    """Request to update task status."""
    status: str  # 'pending', 'completed', 'skipped'


class TaskResponse(BaseModel):
    """Task response model."""
    id: str
    date: str
    day: str
    time_slot: str
    course_name: Optional[str]
    task_type: str
    status: str


class PlanResponse(BaseModel):
    """Study plan response."""
    week_start: str
    total_tasks: int
    completed_tasks: int
    tasks: List[TaskResponse]


class CourseResponse(BaseModel):
    """Course response model."""
    id: str
    name: str
    type: str
    coefficient: float
    cc_percent: float
    ex_percent: float
    content_volume: int


# Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Study Planner API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}


@app.post("/generate-plan")
async def generate_plan(request: GeneratePlanRequest = GeneratePlanRequest()):
    """Generate a new weekly study plan.

    Runs the full pipeline:
    1. Ingests all course materials
    2. Calculates priorities
    3. Calculates balance constraints
    4. Generates study plan via LLM
    5. Saves to Supabase

    Returns:
        Summary of generated plan
    """
    try:
        periode_path = Path(r"C:\study-agent-planner\Periode-1")

        if not periode_path.exists():
            raise HTTPException(status_code=500, detail="Course materials path not found")

        pipeline = StudyPlannerPipeline(str(periode_path))
        result = pipeline.run(
            skip_embeddings=request.skip_embeddings,
            save_to_db=True
        )

        return {
            "status": "success",
            "message": "Study plan generated and saved to database",
            "week_start": result['plan']['week_start'],
            "total_study_hours": result['plan']['total_study_hours'],
            "courses_processed": len(result['courses_data']),
            "priorities": [
                {"rank": p['rank'], "course": p['course'], "score": p['priority_score']}
                for p in result['priorities']
            ],
            "balance": {
                "total_free_hours": result['balance']['total_free_hours'],
                "study_hours": result['balance']['final_study_allocation'],
                "protected_hours": result['balance']['protected_hours']
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating plan: {str(e)}")


@app.get("/plan", response_model=PlanResponse)
async def get_plan(week: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)")):
    """Get the study plan for a specific week.

    Args:
        week: Week start date (optional, defaults to current week)

    Returns:
        Study plan with all tasks
    """
    try:
        db = get_db()

        # Default to current week if not specified
        if not week:
            week = datetime.now().strftime("%Y-%m-%d")

        # Fetch study plan
        tasks = db.get_study_plan(week)

        if not tasks:
            return PlanResponse(
                week_start=week,
                total_tasks=0,
                completed_tasks=0,
                tasks=[]
            )

        # Format response
        task_responses = [
            TaskResponse(
                id=t['id'],
                date=t['date'],
                day=t['day'],
                time_slot=t['time_slot'],
                course_name=t['course_name'],
                task_type=t['task_type'],
                status=t['status']
            )
            for t in tasks
        ]

        completed = sum(1 for t in tasks if t['status'] == 'completed')

        return PlanResponse(
            week_start=week,
            total_tasks=len(tasks),
            completed_tasks=completed,
            tasks=task_responses
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching plan: {str(e)}")


@app.patch("/task/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """Update task status.

    Marks a task as completed, pending, or skipped.
    This data feeds into the Adapter Agent for next week's planning.

    Args:
        task_id: Task UUID
        request: New status

    Returns:
        Updated task info
    """
    try:
        # Validate status
        valid_statuses = ['pending', 'completed', 'skipped']
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )

        db = get_db()
        db.update_task_status(task_id, request.status)

        return {
            "status": "success",
            "task_id": task_id,
            "new_status": request.status
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating task: {str(e)}")


@app.get("/courses")
async def get_courses():
    """Get all courses with their metadata.

    Returns:
        List of all courses
    """
    try:
        db = get_db()
        courses = db.client.table('courses').select('*').execute()

        return {
            "total": len(courses.data),
            "courses": [
                CourseResponse(
                    id=c['id'],
                    name=c['name'],
                    type=c['type'],
                    coefficient=c['coefficient'],
                    cc_percent=c['cc_percent'],
                    ex_percent=c['ex_percent'],
                    content_volume=c['content_volume']
                )
                for c in courses.data
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching courses: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get study statistics for the current week.

    Returns:
        Statistics about completed/pending tasks
    """
    try:
        db = get_db()
        week = datetime.now().strftime("%Y-%m-%d")

        tasks = db.get_study_plan(week)

        if not tasks:
            return {"message": "No tasks found for current week"}

        total = len(tasks)
        completed = sum(1 for t in tasks if t['status'] == 'completed')
        pending = sum(1 for t in tasks if t['status'] == 'pending')
        skipped = sum(1 for t in tasks if t['status'] == 'skipped')

        # Per-course stats
        course_stats = {}
        for t in tasks:
            course = t['course_name'] or 'Protected'
            if course not in course_stats:
                course_stats[course] = {'total': 0, 'completed': 0}
            course_stats[course]['total'] += 1
            if t['status'] == 'completed':
                course_stats[course]['completed'] += 1

        return {
            "week": week,
            "overall": {
                "total": total,
                "completed": completed,
                "pending": pending,
                "skipped": skipped,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0
            },
            "by_course": course_stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


# Run with: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
