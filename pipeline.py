"""Pipeline - Orchestrates all agents to generate weekly study plan."""

from typing import List, Dict
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent / "agents"))

from batch_ingestion_agent import ingest_course
from lightweight_agent import process_lightweight
from embeddings_topics_agent import EmbeddingsTopicsAgent
from priority_agent import calculate_priorities, CourseMetadata
from balance_agent import calculate_balance
from planner_agent import generate_study_plan
from database import get_db

load_dotenv()


class StudyPlannerPipeline:
    """Orchestrates the full study planning pipeline."""

    def __init__(self, periode_path: str):
        """Initialize pipeline with path to course materials.

        Args:
            periode_path: Path to Periode-1 folder
        """
        self.periode_path = Path(periode_path)
        self.embeddings_agent = EmbeddingsTopicsAgent()

        # Course metadata from programme_AIM.md (P1 courses only)
        self.course_metadata = {
            "Computer vision et applications": {
                "coefficient": 3.0,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "Machine Learning & bases massives MM": {
                "coefficient": 3.0,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "Données spatiale_ traitement, analyse et applications": {
                "coefficient": 3.0,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "Fondements du Web of Things": {
                "coefficient": 3.0,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "MLOps for IoT Edges": {
                "coefficient": 3.0,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "Fintech": {
                "coefficient": 1.5,
                "cc_percent": 0,
                "ex_percent": 100,
                "type": "cours"
            },
            "Indexation et recherche dans des bases massives MM": {
                "coefficient": 3.0,
                "cc_percent": 100,
                "ex_percent": 0,
                "type": "at"
            },
            "Projet Tutoré": {
                "coefficient": 1.0,
                "cc_percent": 100,
                "ex_percent": 0,
                "type": "pr"
            }
        }

        # Free time slots from emploi_du_temps.md (evenings and weekends)
        self.free_slots = self._extract_free_slots()

    def _extract_free_slots(self) -> List[Dict]:
        """Extract free time slots from schedule.

        Based on emploi_du_temps.md:
        - Weekdays: after 16:15 (classes end at 16:15)
        - Weekends: full day available

        Returns:
            List of free time slots
        """
        slots = []

        # Weekday evenings (after classes end at 16:15)
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in weekdays:
            # Evening slot: 18:00-21:00 (3 hours)
            slots.append({
                'day': day,
                'start_time': '18:00',
                'end_time': '21:00',
                'hours': 3
            })

        # Weekend (Saturday and Sunday)
        for day in ['Saturday', 'Sunday']:
            # Morning: 10:00-13:00
            slots.append({
                'day': day,
                'start_time': '10:00',
                'end_time': '13:00',
                'hours': 3
            })
            # Afternoon: 14:00-17:00
            slots.append({
                'day': day,
                'start_time': '14:00',
                'end_time': '17:00',
                'hours': 3
            })

        return slots

    def run(self, skip_embeddings: bool = True, save_to_db: bool = False) -> Dict:
        """Run the full pipeline.

        Args:
            skip_embeddings: Skip embedding generation (faster for testing)

        Args:
            skip_embeddings: Skip embedding generation (faster for testing)
            save_to_db: Save results to Supabase database

        Returns:
            Dict with weekly study plan
        """
        print("=" * 70)
        print("STUDY PLANNER PIPELINE")
        print("=" * 70)

        # Step 1: Ingest all courses
        print("\n[1/5] INGESTING COURSES...")
        courses_data = self._ingest_all_courses()

        # Step 2: Generate embeddings (optional)
        if not skip_embeddings:
            print("\n[2/5] GENERATING EMBEDDINGS...")
            embeddings_data = self._generate_embeddings(courses_data)
        else:
            print("\n[2/5] SKIPPING EMBEDDINGS (skip_embeddings=True)")

        # Step 3: Calculate priorities (runs in parallel with balance)
        print("\n[3/5] CALCULATING PRIORITIES...")
        priorities = self._calculate_priorities(courses_data)

        # Step 4: Calculate balance constraints (runs in parallel with priority)
        print("\n[4/5] CALCULATING BALANCE CONSTRAINTS...")
        total_volume = sum(c['total_pages'] for c in courses_data.values())
        balance = calculate_balance(
            self.free_slots,
            course_count=len([c for c in courses_data.values() if c['type'] != 'pr']),
            total_content_volume=total_volume
        )

        # Step 5: Generate study plan
        print("\n[5/5] GENERATING STUDY PLAN...")
        plan = generate_study_plan(priorities, balance, self.free_slots)

        # Step 6: Save to database (optional)
        if save_to_db:
            print("\n[6/6] SAVING TO DATABASE...")
            self._save_to_db(courses_data, plan)
        else:
            print("\n[6/6] SKIPPING DATABASE SAVE (save_to_db=False)")

        return {
            'courses_data': courses_data,
            'priorities': priorities,
            'balance': balance,
            'plan': plan
        }

    def _ingest_all_courses(self) -> Dict:
        """Ingest all courses from Periode-1.

        Returns:
            Dict with course name -> ingestion data
        """
        courses_data = {}

        # Map folder names to course names
        folder_map = {
            "Computer vision et applications": "Computer vision et applications",
            "Fintech": "Fintech",
            "Fondements du Web of Things": "Fondements du Web of Things",
            "MLOps for IoT Edges": "MLOps for IoT Edges",
            "Données spatiale_ traitement, analyse et applications": "Données spatiale_ traitement, analyse et applications",
            "Machine Learning & bases massives MM": "Machine Learning & bases massives MM"
        }

        for folder_name, course_name in folder_map.items():
            course_path = self.periode_path / folder_name / "Cours"

            if not course_path.exists():
                # Try without "Cours" subfolder
                course_path = self.periode_path / folder_name

            if not course_path.exists():
                print(f"  [SKIP] {course_name} - folder not found")
                continue

            # Find all PDFs in course folder
            pdfs = list(course_path.glob("**/*.pdf"))

            # Skip very large files (like the MLOps Design Patterns book - 335MB)
            # But allow Computer Vision (15MB) since it's the main course
            pdfs = [p for p in pdfs if p.stat().st_size < 50_000_000]  # < 50MB

            if not pdfs:
                print(f"  [SKIP] {course_name} - no PDFs found")
                continue

            total_pages = 0
            for pdf in pdfs:
                try:
                    result = ingest_course(str(pdf))
                    total_pages += result['total_slides']
                except Exception as e:
                    print(f"  [ERROR] {pdf.name}: {e}")

            metadata = self.course_metadata.get(course_name, {})
            courses_data[course_name] = {
                'total_pages': total_pages,
                'coefficient': metadata.get('coefficient', 2.0),
                'cc_percent': metadata.get('cc_percent', 50),
                'ex_percent': metadata.get('ex_percent', 50),
                'type': metadata.get('type', 'cours')
            }

            print(f"  [OK] {course_name}: {total_pages} pages")

        return courses_data

    def _generate_embeddings(self, courses_data: Dict) -> Dict:
        """Generate embeddings for all courses.

        Args:
            courses_data: Ingestion data

        Returns:
            Dict with embeddings data
        """
        embeddings_data = {}

        for course_name, data in courses_data.items():
            if data['type'] == 'pr':  # Skip projects
                continue

            # This would process actual slides - skipped for now
            embeddings_data[course_name] = {
                'embedding_dimension': 384,
                'topics': []
            }

        return embeddings_data

    def _calculate_priorities(self, courses_data: Dict) -> List[Dict]:
        """Calculate priorities for all courses.

        Args:
            courses_data: Ingestion data with metadata

        Returns:
            List of priority dicts sorted by score
        """
        courses = []

        for name, data in courses_data.items():
            # Skip "Projet Tutoré" - it's a project, not a course to study
            if data['type'] == 'pr':
                continue

            courses.append({
                'name': name,
                'coefficient': data['coefficient'],
                'cc_percent': data['cc_percent'],
                'ex_percent': data['ex_percent'],
                'content_volume': data['total_pages'],
                'course_type': data['type']
            })

        return calculate_priorities(courses)

    def _save_to_db(self, courses_data: Dict, plan: Dict):
        """Save results to Supabase database.

        Args:
            courses_data: Ingested course data
            plan: Generated study plan
        """
        try:
            db = get_db()
            from datetime import datetime

            # Insert courses
            course_ids = {}
            for name, data in courses_data.items():
                # Check if course exists
                existing = db.get_course_by_name(name)
                if existing:
                    course_ids[name] = existing['id']
                else:
                    course_id = db.insert_course({
                        'name': name,
                        'type': data['type'],
                        'period': 'P1',
                        'coefficient': data['coefficient'],
                        'cc_percent': data['cc_percent'],
                        'ex_percent': data['ex_percent'],
                        'content_volume': data['total_pages']
                    })
                    course_ids[name] = course_id
                    print(f"  [DB] Inserted course: {name}")

            # Clear existing study plan for this week
            week_start = plan['week_start']
            db.clear_study_plan(week_start)
            print(f"  [DB] Cleared existing plan for {week_start}")

            # Insert study plan
            plan_entries = []
            for item in plan['plan']:
                if 'day' in item:
                    course_name = item.get('course', '')
                    course_id = course_ids.get(course_name)

                    # Determine task type
                    task_type = item.get('task_type', 'revision')
                    if 'Protected' in course_name or 'Hobby' in course_name:
                        task_type = 'protected'

                    plan_entries.append({
                        'date': week_start,
                        'day': item['day'],
                        'time_slot': item.get('time', ''),
                        'course_id': course_id,
                        'course_name': course_name if task_type != 'protected' else None,
                        'task_type': task_type,
                        'status': 'pending'
                    })

            if plan_entries:
                count = db.insert_study_plan(plan_entries)
                print(f"  [DB] Inserted {count} study plan entries")

            print("  [DB] Save complete!")

        except Exception as e:
            print(f"  [DB ERROR] {e}")
            print("  [DB] Continuing without database save...")

    def print_results(self, result: Dict):
        """Print pipeline results.

        Args:
            result: Pipeline output
        """
        print("\n" + "=" * 70)
        print("PIPELINE RESULTS")
        print("=" * 70)

        # Print priorities
        print("\nCOURSE PRIORITIES:")
        print("-" * 70)
        print(f"{'Rank':<5} {'Course':<40} {'Score':<10} {'Pages':<8}")
        print("-" * 70)
        for p in result['priorities']:
            print(f"{p['rank']:<5} {p['course']:<40} {p['priority_score']:<10.4f} {p['content_volume']:<8}")

        # Print balance
        print("\nBALANCE CONSTRAINTS:")
        print("-" * 70)
        balance = result['balance']
        print(f"Total free hours: {balance['total_free_hours']}h")
        print(f"Max study hours (65%): {balance['max_study_hours']}h")
        print(f"Protected hours: {balance['protected_hours']}h")
        print(f"Final study allocation: {balance['final_study_allocation']}h")

        print("\nProtected blocks:")
        for block in balance['protected_blocks']:
            print(f"  - {block['day']} {block['start_time']}-{block['end_time']}: {block['reason']}")

        # Print plan
        print("\nWEEKLY STUDY PLAN:")
        print("-" * 70)
        plan = result['plan']
        print(f"Week: {plan['week_start']}")
        print(f"Total study hours: {plan['total_study_hours']}h")
        print("\nSchedule:")

        # Group by day
        if isinstance(plan['plan'], list):
            for item in plan['plan']:
                if 'day' in item:
                    course = item.get('course', 'N/A')
                    time = item.get('time', 'N/A')
                    task_type = item.get('task_type', 'revision')

                    # Mark protected blocks
                    if task_type == 'protected' or 'Protected' in course or 'Hobby' in course:
                        print(f"  {item['day']:12} {time:15} [PROTECTED]")
                    else:
                        print(f"  {item['day']:12} {time:15} {course}")

        print("\n" + "=" * 70)
        print(f"Summary: {plan.get('summary', 'N/A')}")
        print("=" * 70)


def main():
    """Run the pipeline with real data."""
    import argparse

    parser = argparse.ArgumentParser(description='Study Planner Pipeline')
    parser.add_argument('--db', action='store_true', help='Save results to database')
    parser.add_argument('--embeddings', action='store_true', help='Generate embeddings')
    args = parser.parse_args()

    periode_path = r"C:\study-agent-planner\Periode-1"

    pipeline = StudyPlannerPipeline(periode_path)
    result = pipeline.run(
        skip_embeddings=not args.embeddings,
        save_to_db=args.db
    )
    pipeline.print_results(result)

    return result


if __name__ == "__main__":
    main()
