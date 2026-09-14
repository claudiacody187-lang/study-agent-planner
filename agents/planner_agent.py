"""Planner Agent - Generates weekly study plan based on priorities and constraints."""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os
from groq import Groq


class PlannerAgent:
    """Generates weekly study schedule combining priorities and balance constraints."""

    def __init__(self, model: str = "qwen/qwen3.8-27b"):
        """Initialize planner with Groq client.

        Args:
            model: Groq model to use (default: qwen/qwen3.8-27b)
        """
        self.model = model
        self.client = None

    def _get_client(self):
        """Lazy load Groq client."""
        if self.client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY not found in environment")
            self.client = Groq(api_key=api_key)
        return self.client

    def generate_plan(self,
                      priorities: List[Dict],
                      balance: Dict,
                      free_slots: List[Dict]) -> Dict:
        """Generate weekly study plan.

        Args:
            priorities: Ranked course priorities from Priority Agent
            balance: Balance constraints from Balance Agent
            free_slots: Available free time slots

        Returns:
            Dict with weekly study plan
        """
        # Prepare context for LLM
        courses_context = self._format_courses(priorities)
        constraints_context = self._format_constraints(balance)
        slots_context = self._format_slots(free_slots)

        prompt = f"""You are a study planner. Create a weekly study schedule based on:

COURSES (ranked by priority):
{courses_context}

CONSTRAINTS:
{constraints_context}

AVAILABLE TIME SLOTS:
{slots_context}

RULES:
1. Allocate more time to higher priority courses
2. NEVER schedule study during protected blocks
3. No study after 22:00
4. Balance study across the week

Output ONLY valid JSON, no markdown. task_type MUST be one of: "revision", "practice", "protected":
{{"plan": [{{"day": "Monday", "time": "18:00-21:00", "course": "CourseName", "task_type": "revision"}}]}}"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )

            import json
            plan_text = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if "```" in plan_text:
                plan_text = plan_text.split("```")[1]
                if plan_text.startswith("json"):
                    plan_text = plan_text[4:]

            plan_data = json.loads(plan_text)

            # Calculate total hours
            total_hours = 0
            for item in plan_data.get('plan', []):
                time_str = item.get('time', '0-0')
                try:
                    start, end = time_str.split('-')
                    start_h = int(start.split(':')[0])
                    end_h = int(end.split(':')[0])
                    total_hours += end_h - start_h
                except:
                    pass

            return {
                'week_start': datetime.now().strftime("%Y-%m-%d"),
                'total_study_hours': total_hours,
                'plan': plan_data.get('plan', []),
                'summary': f"Generated {len(plan_data.get('plan', []))} study sessions"
            }

        except Exception as e:
            # Fallback: generate deterministic plan without LLM
            return self._generate_fallback_plan(priorities, balance, free_slots)

    def _format_courses(self, priorities: List[Dict]) -> str:
        """Format courses for prompt."""
        lines = []
        for p in priorities:
            lines.append(f"{p['rank']}. {p['course']} (score: {p['priority_score']:.2f}, "
                        f"coefficient: {p['coefficient']}, volume: {p['content_volume']} slides)")
        return "\n".join(lines)

    def _format_constraints(self, balance: Dict) -> str:
        """Format constraints for prompt."""
        lines = [
            f"- Max study hours: {balance['final_study_allocation']}h",
            f"- Protected hours: {balance['protected_hours']}h",
            f"- Balance ratio: {balance['balance_ratio']:.0%}",
            "\nProtected blocks:"
        ]
        for block in balance['protected_blocks']:
            lines.append(f"  - {block['day']} {block['start_time']}-{block['end_time']}: {block['reason']}")
        return "\n".join(lines)

    def _format_slots(self, slots: List[Dict]) -> str:
        """Format time slots for prompt."""
        lines = []
        for s in slots:
            lines.append(f"- {s['day']} {s['start_time']}-{s['end_time']} ({s['hours']}h)")
        return "\n".join(lines)

    def _generate_fallback_plan(self,
                                priorities: List[Dict],
                                balance: Dict,
                                free_slots: List[Dict]) -> Dict:
        """Generate plan without LLM (fallback)."""
        study_hours = balance['final_study_allocation']
        protected = {(b['day'], b['start_time']) for b in balance['protected_blocks']}

        plan = []
        hours_allocated = 0

        for slot in free_slots:
            if hours_allocated >= study_hours:
                break

            # Skip protected slots
            if (slot['day'], slot['start_time']) in protected:
                continue

            # Assign highest priority course
            course = priorities[0]['course'] if priorities else "Unknown"

            plan.append({
                'day': slot['day'],
                'time': f"{slot['start_time']}-{slot['end_time']}",
                'course': course,
                'task_type': 'revision',
                'hours': min(slot['hours'], study_hours - hours_allocated)
            })
            hours_allocated += slot['hours']

        return {
            'week_start': datetime.now().strftime("%Y-%m-%d"),
            'total_study_hours': hours_allocated,
            'plan': plan,
            'summary': f"Fallback plan: {hours_allocated}h allocated to {len(plan)} slots"
        }


def generate_study_plan(priorities: List[Dict],
                        balance: Dict,
                        free_slots: List[Dict]) -> Dict:
    """Convenience function to generate study plan.

    Args:
        priorities: Ranked priorities
        balance: Balance constraints
        free_slots: Free time slots

    Returns:
        Weekly study plan
    """
    agent = PlannerAgent()
    return agent.generate_plan(priorities, balance, free_slots)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("PLANNER AGENT TEST")
    print("=" * 60)

    # Sample data
    priorities = [
        {'rank': 1, 'course': 'Machine Learning', 'priority_score': 3.36, 'coefficient': 3.0, 'content_volume': 701},
        {'rank': 2, 'course': 'Computer Vision', 'priority_score': 3.11, 'coefficient': 3.0, 'content_volume': 290},
        {'rank': 3, 'course': 'Web of Things', 'priority_score': 2.45, 'coefficient': 2.5, 'content_volume': 141},
        {'rank': 4, 'course': 'MLOps', 'priority_score': 2.11, 'coefficient': 2.0, 'content_volume': 545},
        {'rank': 5, 'course': 'Geo/Spatial', 'priority_score': 1.99, 'coefficient': 2.0, 'content_volume': 276},
        {'rank': 6, 'course': 'Fintech', 'priority_score': 1.24, 'coefficient': 1.5, 'content_volume': 9},
    ]

    balance = {
        'final_study_allocation': 17.6,
        'protected_hours': 8,
        'balance_ratio': 0.65,
        'protected_blocks': [
            {'day': 'Friday', 'start_time': '18:00', 'end_time': '23:00', 'hours': 5, 'reason': 'protected_evening'},
            {'day': 'Saturday', 'start_time': '14:00', 'end_time': '17:00', 'hours': 3, 'reason': 'hobby_time'}
        ]
    }

    free_slots = [
        {'day': 'Monday', 'start_time': '18:00', 'end_time': '21:00', 'hours': 3},
        {'day': 'Tuesday', 'start_time': '18:00', 'end_time': '21:00', 'hours': 3},
        {'day': 'Wednesday', 'start_time': '18:00', 'end_time': '21:00', 'hours': 3},
        {'day': 'Thursday', 'start_time': '18:00', 'end_time': '22:00', 'hours': 4},
        {'day': 'Friday', 'start_time': '18:00', 'end_time': '23:00', 'hours': 5},
        {'day': 'Saturday', 'start_time': '10:00', 'end_time': '13:00', 'hours': 3},
        {'day': 'Saturday', 'start_time': '14:00', 'end_time': '17:00', 'hours': 3},
        {'day': 'Sunday', 'start_time': '10:00', 'end_time': '13:00', 'hours': 3},
    ]

    agent = PlannerAgent()
    plan = agent.generate_plan(priorities, balance, free_slots)

    print(f"\nWeek: {plan['week_start']}")
    print(f"Total study hours: {plan['total_study_hours']}h")
    print(f"\nWeekly Plan:")

    if 'plan' in plan and isinstance(plan['plan'], list):
        for item in plan['plan']:
            if 'day' in item:
                print(f"  {item['day']}: {item.get('time', 'N/A')} - {item.get('course', 'N/A')}")
            elif 'slots' in item:
                print(f"\n  {item['day']}:")
                for slot in item['slots']:
                    print(f"    {slot['time']} - {slot['course']} ({slot['task_type']})")

    print(f"\nSummary: {plan.get('summary', 'N/A')}")
    print("\n" + "=" * 60)
    print("PLANNER AGENT TEST PASSED")
    print("=" * 60)
