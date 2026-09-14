-- Study Planner Database Schema
-- Run this in Supabase SQL Editor

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
create index if not exists idx_study_plan_status on study_plan(status);
create index if not exists idx_embeddings_course on embeddings(course_id);

-- Row Level Security (RLS) policies
alter table courses enable row level security;
alter table study_plan enable row level security;
alter table embeddings enable row level security;

-- Allow all operations for authenticated users
create policy "Allow all for authenticated users" on courses
    for all using (auth.role() = 'authenticated');

create policy "Allow all for authenticated users" on study_plan
    for all using (auth.role() = 'authenticated');

create policy "Allow all for authenticated users" on embeddings
    for all using (auth.role() = 'authenticated');
