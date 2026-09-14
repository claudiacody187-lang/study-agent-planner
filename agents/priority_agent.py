"""Priority Agent - Calculates study priorities based on exam weight, CC weight, and content volume."""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class CourseMetadata:
    """Course metadata for priority calculation."""
    name: str
    coefficient: float
    cc_percent: float  # Continuous control percentage (0-100)
    ex_percent: float  # Exam percentage (0-100)
    content_volume: int  # Number of slides/pages
    course_type: str = "cours"  # cours, td, tp, at, pr


class PriorityAgent:
    """Calculates priority scores for courses based on multiple factors."""

    def __init__(self,
                 ex_weight: float = 1.0,
                 cc_weight: float = 0.7,
                 volume_weight: float = 0.3):
        """Initialize priority agent with weights.

        Args:
            ex_weight: Weight for exam percentage (default: 1.0)
            cc_weight: Weight for CC percentage (default: 0.7 - CC is usually easier)
            volume_weight: Weight for content volume factor (default: 0.3)
        """
        self.ex_weight = ex_weight
        self.cc_weight = cc_weight
        self.volume_weight = volume_weight

    def calculate_priority(self, course: CourseMetadata) -> Dict:
        """Calculate priority score for a single course.

        Priority formula:
        score = coefficient × (ex_percent × ex_weight + cc_percent × cc_weight) × volume_factor

        Args:
            course: CourseMetadata object

        Returns:
            Dict with course name, priority score, and breakdown
        """
        # Normalize percentages to 0-1
        ex_factor = course.ex_percent / 100.0
        cc_factor = course.cc_percent / 100.0

        # Assessment weight (exam + CC)
        assessment_score = (ex_factor * self.ex_weight + cc_factor * self.cc_weight)

        # Volume factor: more content = higher priority (but logarithmic to avoid extreme values)
        # Normalized around 100 slides as baseline
        import math
        volume_factor = 1.0 + self.volume_weight * math.log10(max(course.content_volume, 1) / 100.0 + 1)

        # Final priority score
        priority_score = course.coefficient * assessment_score * volume_factor

        return {
            'course': course.name,
            'priority_score': round(priority_score, 4),
            'coefficient': course.coefficient,
            'ex_percent': course.ex_percent,
            'cc_percent': course.cc_percent,
            'content_volume': course.content_volume,
            'breakdown': {
                'assessment_score': round(assessment_score, 4),
                'volume_factor': round(volume_factor, 4)
            }
        }

    def rank_courses(self, courses: List[CourseMetadata]) -> List[Dict]:
        """Calculate priorities and rank courses from highest to lowest.

        Args:
            courses: List of CourseMetadata objects

        Returns:
            List of priority dicts sorted by priority_score descending
        """
        priorities = [self.calculate_priority(c) for c in courses]
        priorities.sort(key=lambda x: x['priority_score'], reverse=True)

        # Add rank
        for i, p in enumerate(priorities, 1):
            p['rank'] = i

        return priorities


def calculate_priorities(courses: List[Dict]) -> List[Dict]:
    """Convenience function to calculate priorities from dict input.

    Args:
        courses: List of dicts with course metadata

    Returns:
        List of priority dicts sorted by score
    """
    agent = PriorityAgent()
    course_objs = [
        CourseMetadata(
            name=c['name'],
            coefficient=c['coefficient'],
            cc_percent=c.get('cc_percent', 50),
            ex_percent=c.get('ex_percent', 50),
            content_volume=c.get('content_volume', 100),
            course_type=c.get('course_type', 'cours')
        )
        for c in courses
    ]
    return agent.rank_courses(course_objs)


if __name__ == "__main__":
    # Quick test with sample courses
    courses = [
        CourseMetadata("Computer Vision", 3.0, 40, 60, 290),
        CourseMetadata("Geo/Spatial", 2.0, 50, 50, 276),
        CourseMetadata("Web of Things", 2.5, 40, 60, 141),
        CourseMetadata("MLOps", 2.0, 50, 50, 545),
        CourseMetadata("Fintech", 1.5, 60, 40, 9),
        CourseMetadata("Machine Learning", 3.0, 40, 60, 701),
    ]

    agent = PriorityAgent()
    priorities = agent.rank_courses(courses)

    print("=" * 70)
    print("COURSE PRIORITIES (highest to lowest)")
    print("=" * 70)
    print(f"{'Rank':<5} {'Course':<20} {'Score':<10} {'Coef':<6} {'EX%':<6} {'CC%':<6} {'Vol':<6}")
    print("-" * 70)
    for p in priorities:
        print(f"{p['rank']:<5} {p['course']:<20} {p['priority_score']:<10.4f} {p['coefficient']:<6.1f} "
              f"{p['ex_percent']:<6.0f} {p['cc_percent']:<6.0f} {p['content_volume']:<6}")
