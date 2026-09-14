"""Database module - Supabase connection and operations."""

import os
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class Database:
    """Supabase database wrapper for study planner."""

    def __init__(self):
        """Initialize Supabase client."""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

        self.client: Client = create_client(self.url, self.key)

    def setup_schema(self):
        """Create database tables if they don't exist.

        Run this once to set up the schema.
        """
        schema_sql = """
        -- Enable vector extension
        create extension if not exists vector;

        -- Courses table
        create table if not exists courses (
            id uuid primary key default gen_random_uuid(),
            name text not null,
            type text check (type in ('cours','td','tp','at','pr')),
            period text,
            coefficient numeric,
            cc_percent numeric,
            ex_percent numeric,
            content_volume integer,
            created_at timestamp default now()
        );

        -- Schedule slots table
        create table if not exists schedule_slots (
            id uuid primary key default gen_random_uuid(),
            day text,
            start_time time,
            end_time time,
            course_id uuid references courses(id),
            is_free boolean default false,
            created_at timestamp default now()
        );

        -- Embeddings table
        create table if not exists embeddings (
            id uuid primary key default gen_random_uuid(),
            course_id uuid references courses(id),
            content text,
            embedding vector(384),  -- matches all-MiniLM-L6-v2 dimension
            slide_number integer,
            created_at timestamp default now()
        );

        -- Study plan table
        create table if not exists study_plan (
            id uuid primary key default gen_random_uuid(),
            date date,
            day text,
            time_slot text,
            course_id uuid references courses(id),
            course_name text,
            task_type text check (task_type in ('revision','practice','project','protected')),
            status text default 'pending',
            created_at timestamp default now()
        );

        -- Create indexes for better query performance
        create index if not exists idx_courses_name on courses(name);
        create index if not exists idx_study_plan_date on study_plan(date);
        create index if not exists idx_embeddings_course on embeddings(course_id);
        """

        # Execute via RPC
        try:
            self.client.rpc('exec_sql', {'query': schema_sql}).execute()
            print("Schema created successfully")
        except Exception as e:
            # Fallback: execute table by table via REST API
            print(f"Note: Schema setup requires SQL editor access. Error: {e}")
            print("Please run the schema SQL in Supabase SQL Editor manually.")

    def insert_course(self, course: Dict) -> str:
        """Insert a course and return its ID.

        Args:
            course: Course data dict

        Returns:
            Course UUID
        """
        result = self.client.table('courses').insert(course).execute()
        return result.data[0]['id']

    def get_course_by_name(self, name: str) -> Optional[Dict]:
        """Get course by name.

        Args:
            name: Course name

        Returns:
            Course dict or None
        """
        result = self.client.table('courses').select('*').eq('name', name).execute()
        return result.data[0] if result.data else None

    def insert_study_plan(self, plan: List[Dict]) -> int:
        """Insert study plan entries.

        Args:
            plan: List of plan entries

        Returns:
            Number of entries inserted
        """
        result = self.client.table('study_plan').insert(plan).execute()
        return len(result.data)

    def get_study_plan(self, date: str = None) -> List[Dict]:
        """Get study plan for a specific date or week.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            List of plan entries
        """
        query = self.client.table('study_plan').select('*')

        if date:
            query = query.eq('date', date)

        result = query.execute()
        return result.data

    def update_task_status(self, task_id: str, status: str):
        """Update task status.

        Args:
            task_id: Task UUID
            status: New status ('pending', 'completed', 'skipped')
        """
        self.client.table('study_plan').update({'status': status}).eq('id', task_id).execute()

    def clear_study_plan(self, week_start: str = None):
        """Clear study plan for a specific week.

        Args:
            week_start: Week start date (optional, clears all if not provided)
        """
        if week_start:
            self.client.table('study_plan').delete().eq('date', week_start).execute()
        else:
            self.client.table('study_plan').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

    def insert_embedding(self, course_id: str, content: str, embedding: List[float], slide_number: int = None):
        """Insert an embedding.

        Args:
            course_id: Course UUID
            content: Text content
            embedding: Vector embedding
            slide_number: Slide number (optional)
        """
        self.client.table('embeddings').insert({
            'course_id': course_id,
            'content': content,
            'embedding': embedding,
            'slide_number': slide_number
        }).execute()

    def get_embeddings_for_course(self, course_id: str) -> List[Dict]:
        """Get all embeddings for a course.

        Args:
            course_id: Course UUID

        Returns:
            List of embedding records
        """
        result = self.client.table('embeddings').select('*').eq('course_id', course_id).execute()
        return result.data


def get_db() -> Database:
    """Get database instance.

    Returns:
        Database instance
    """
    return Database()


if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    try:
        db = get_db()
        print(f"Connected to Supabase: {db.url}")

        # Try a simple query
        result = db.client.table('courses').select('count').execute()
        print("Connection successful!")

        print("\nTo set up the schema, run the SQL in database/schema.sql in Supabase SQL Editor.")

    except Exception as e:
        print(f"Connection failed: {e}")
