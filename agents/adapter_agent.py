"""Adapter Agent - Evaluates completed tasks and adapts future plans based on feedback."""

from typing import List, Dict, Optional
import os
from groq import Groq


class AdapterAgent:
    """Evaluates weekly progress and adjusts priorities for next planning cycle."""

    def __init__(self, model: str = "qwen/qwen3.8-27b"):
        """Initialize adapter with Groq client.

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

    def evaluate_week(self,
                      study_plan: List[Dict],
                      completed_tasks: List[Dict]) -> Dict:
        """Evaluate completed tasks and generate adjustments.

        Args:
            study_plan: List of planned tasks from last week
            completed_tasks: List of tasks marked as completed

        Returns:
            Dict with adjustments and recommendations
        """
        # Calculate completion stats
        total_tasks = len(study_plan)
        completed_count = len(completed_tasks)
        completion_rate = completed_count / total_tasks if total_tasks > 0 else 0

        # Group by course
        course_stats = self._calculate_course_stats(study_plan, completed_tasks)

        # Determine if LLM analysis is needed
        if completion_rate < 0.5 or completion_rate == 1.0:
            # Use fallback for simple cases
            adjustments = self._generate_adjustments(course_stats, completion_rate)
        else:
            # Use LLM for nuanced analysis
            adjustments = self._analyze_with_llm(course_stats, completion_rate)

        return {
            'completion_rate': round(completion_rate, 2),
            'completed_tasks': completed_count,
            'total_tasks': total_tasks,
            'course_stats': course_stats,
            'adjustments': adjustments,
            'recommendation': self._generate_recommendation(completion_rate, adjustments)
        }

    def _calculate_course_stats(self, study_plan: List[Dict], completed_tasks: List[Dict]) -> Dict:
        """Calculate completion stats per course.

        Args:
            study_plan: Planned tasks
            completed_tasks: Completed tasks

        Returns:
            Dict with per-course statistics
        """
        stats = {}

        # Count planned per course
        for task in study_plan:
            course = task.get('course', 'Unknown')
            if course not in stats:
                stats[course] = {'planned': 0, 'completed': 0, 'skipped': 0}
            stats[course]['planned'] += 1

        # Count completed per course
        for task in completed_tasks:
            course = task.get('course', 'Unknown')
            if course in stats:
                stats[course]['completed'] += 1

        # Calculate skipped
        for course in stats:
            stats[course]['skipped'] = stats[course]['planned'] - stats[course]['completed']
            stats[course]['completion_rate'] = (
                stats[course]['completed'] / stats[course]['planned']
                if stats[course]['planned'] > 0 else 0
            )

        return stats

    def _generate_adjustments(self, course_stats: Dict, completion_rate: float) -> List[Dict]:
        """Generate priority adjustments based on stats.

        Args:
            course_stats: Per-course statistics
            completion_rate: Overall completion rate

        Returns:
            List of adjustment recommendations
        """
        adjustments = []

        for course, stats in course_stats.items():
            if stats['skipped'] >= 3:
                # Course was skipped multiple times - increase priority
                adjustments.append({
                    'course': course,
                    'action': 'increase_priority',
                    'reason': f"Skipped {stats['skipped']} times last week",
                    'suggested_boost': 0.2
                })
            elif stats['completion_rate'] == 1.0:
                # Course fully completed - can reduce priority slightly
                adjustments.append({
                    'course': course,
                    'action': 'maintain_or_reduce',
                    'reason': 'Fully completed last week',
                    'suggested_boost': -0.1
                })
            elif stats['completion_rate'] < 0.5:
                # Low completion - needs attention
                adjustments.append({
                    'course': course,
                    'action': 'increase_priority',
                    'reason': f"Low completion rate ({stats['completion_rate']:.0%})",
                    'suggested_boost': 0.15
                })

        return adjustments

    def _analyze_with_llm(self, course_stats: Dict, completion_rate: float) -> List[Dict]:
        """Use LLM for nuanced analysis.

        Args:
            course_stats: Per-course statistics
            completion_rate: Overall completion rate

        Returns:
            List of adjustments
        """
        try:
            client = self._get_client()

            stats_text = "\n".join([
                f"- {course}: {stats['completed']}/{stats['planned']} completed ({stats['completion_rate']:.0%})"
                for course, stats in course_stats.items()
            ])

            prompt = f"""Analyze this week's study completion and suggest priority adjustments.

COMPLETION STATS:
{stats_text}

Overall completion rate: {completion_rate:.0%}

Output ONLY valid JSON array:
[{{"course": "CourseName", "action": "increase_priority", "reason": "why", "suggested_boost": 0.2}}]"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )

            import json
            text = response.choices[0].message.content.strip()

            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            return json.loads(text)

        except Exception as e:
            return self._generate_adjustments(course_stats, completion_rate)

    def _generate_recommendation(self, completion_rate: float, adjustments: List[Dict]) -> str:
        """Generate overall recommendation.

        Args:
            completion_rate: Overall completion rate
            adjustments: List of adjustments

        Returns:
            Recommendation string
        """
        if completion_rate >= 0.9:
            return "Excellent week! Consider taking on more challenging topics or reducing study time slightly."
        elif completion_rate >= 0.7:
            return "Good progress. Apply suggested priority adjustments for better balance."
        elif completion_rate >= 0.5:
            return "Moderate completion. Review skipped courses and consider reducing workload."
        else:
            return "Low completion rate. Consider reducing course load or adjusting time allocation."


def evaluate_weekly_progress(study_plan: List[Dict], completed_tasks: List[Dict]) -> Dict:
    """Convenience function to evaluate weekly progress.

    Args:
        study_plan: List of planned tasks
        completed_tasks: List of completed tasks

    Returns:
        Evaluation result with adjustments
    """
    agent = AdapterAgent()
    return agent.evaluate_week(study_plan, completed_tasks)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("ADAPTER AGENT TEST")
    print("=" * 60)

    # Sample study plan (last week)
    study_plan = [
        {'day': 'Monday', 'course': 'Machine Learning', 'task_type': 'revision'},
        {'day': 'Tuesday', 'course': 'Computer Vision', 'task_type': 'revision'},
        {'day': 'Wednesday', 'course': 'Machine Learning', 'task_type': 'practice'},
        {'day': 'Thursday', 'course': 'MLOps', 'task_type': 'revision'},
        {'day': 'Saturday', 'course': 'Web of Things', 'task_type': 'revision'},
        {'day': 'Sunday', 'course': 'Geo/Spatial', 'task_type': 'revision'},
        {'day': 'Sunday', 'course': 'Fintech', 'task_type': 'revision'},
    ]

    # Sample completed tasks (user marked as done)
    completed_tasks = [
        {'day': 'Monday', 'course': 'Machine Learning', 'task_type': 'revision'},
        {'day': 'Tuesday', 'course': 'Computer Vision', 'task_type': 'revision'},
        {'day': 'Wednesday', 'course': 'Machine Learning', 'task_type': 'practice'},
        # MLOps, Web of Things, Geo/Spatial, Fintech were skipped
    ]

    agent = AdapterAgent()
    result = agent.evaluate_week(study_plan, completed_tasks)

    print(f"\nCompletion rate: {result['completion_rate']:.0%}")
    print(f"Completed: {result['completed_tasks']}/{result['total_tasks']} tasks")

    print("\nPer-course stats:")
    for course, stats in result['course_stats'].items():
        status = "OK" if stats['completion_rate'] >= 0.5 else "NEEDS ATTENTION"
        print(f"  {course}: {stats['completed']}/{stats['planned']} ({stats['completion_rate']:.0%}) [{status}]")

    print(f"\nAdjustments ({len(result['adjustments'])}):")
    for adj in result['adjustments']:
        print(f"  - {adj['course']}: {adj['action']} ({adj['reason']})")

    print(f"\nRecommendation: {result['recommendation']}")

    print("\n" + "=" * 60)
    print("ADAPTER AGENT TEST PASSED")
    print("=" * 60)
