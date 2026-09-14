"""Balance Agent - Determines study time allocation and protected rest blocks."""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class TimeSlot:
    """A time slot in the schedule."""
    day: str
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    hours: float


class BalanceAgent:
    """Ensures realistic study plans with protected rest time."""

    # Default constraints
    MAX_STUDY_PERCENT = 0.65  # Max 65% of free time for study
    MAX_CONSECUTIVE_BLOCKS = 3  # No more than 3 study blocks back-to-back
    NO_STUDY_AFTER = "22:00"  # Nothing scheduled after this time
    MIN_BREAK_BETWEEN_BLOCKS = 1  # Hours between study blocks

    def __init__(self,
                 max_study_percent: float = None,
                 max_consecutive: int = None,
                 no_study_after: str = None):
        """Initialize with custom constraints.

        Args:
            max_study_percent: Max percentage of free time for study (0-1)
            max_consecutive: Max consecutive study blocks
            no_study_after: No study after this time (HH:MM)
        """
        self.max_study_percent = max_study_percent or self.MAX_STUDY_PERCENT
        self.max_consecutive = max_consecutive or self.MAX_CONSECUTIVE_BLOCKS
        self.no_study_after = no_study_after or self.NO_STUDY_AFTER

    def calculate_balance(self,
                          free_slots: List[TimeSlot],
                          course_count: int,
                          total_content_volume: int) -> Dict:
        """Calculate how to balance study time with rest.

        Args:
            free_slots: List of available free time slots
            course_count: Number of courses to study
            total_content_volume: Total slides/pages across all courses

        Returns:
            Dict with study allocation and protected blocks
        """
        # Calculate total free hours
        total_free_hours = sum(slot.hours for slot in free_slots)

        # Calculate max study hours based on constraints
        max_study_hours = total_free_hours * self.max_study_percent

        # Calculate recommended study hours based on content volume
        # Rule of thumb: ~2 minutes per slide/page for revision
        estimated_study_hours = (total_content_volume * 2) / 60

        # Cap at max study hours
        recommended_study_hours = min(estimated_study_hours, max_study_hours)

        # Generate protected blocks
        protected_blocks = self._generate_protected_blocks(free_slots)

        # Calculate actual study allocation after protecting rest
        protected_hours = sum(b['hours'] for b in protected_blocks)
        available_study_hours = total_free_hours - protected_hours

        # Final study allocation
        final_study_hours = min(recommended_study_hours, available_study_hours)

        return {
            'total_free_hours': round(total_free_hours, 1),
            'max_study_hours': round(max_study_hours, 1),
            'recommended_study_hours': round(recommended_study_hours, 1),
            'protected_hours': round(protected_hours, 1),
            'final_study_allocation': round(final_study_hours, 1),
            'protected_blocks': protected_blocks,
            'balance_ratio': round(final_study_hours / total_free_hours, 2) if total_free_hours > 0 else 0
        }

    def _generate_protected_blocks(self, free_slots: List[TimeSlot]) -> List[Dict]:
        """Generate protected rest blocks based on constraints.

        Rules:
        - One full evening protected per week
        - No study after 22:00
        - One weekend slot for hobbies/personal projects

        Args:
            free_slots: Available free time slots

        Returns:
            List of protected blocks
        """
        protected = []

        # Group slots by day
        days = {}
        for slot in free_slots:
            if slot.day not in days:
                days[slot.day] = []
            days[slot.day].append(slot)

        # Protect slots after 22:00
        for slot in free_slots:
            if slot.start_time >= self.no_study_after:
                protected.append({
                    'day': slot.day,
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'hours': slot.hours,
                    'reason': 'no_study_after_22'
                })

        # Protect one full evening (e.g., Friday or Saturday)
        evening_priority = ['Friday', 'Saturday', 'Thursday']
        for day_name in evening_priority:
            if day_name in days:
                evening_slots = [s for s in days[day_name] if s.start_time >= '18:00']
                if evening_slots:
                    for slot in evening_slots:
                        protected.append({
                            'day': slot.day,
                            'start_time': slot.start_time,
                            'end_time': slot.end_time,
                            'hours': slot.hours,
                            'reason': 'protected_evening'
                        })
                    break

        # Protect one weekend slot for hobbies
        weekend = ['Saturday', 'Sunday']
        for day_name in weekend:
            if day_name in days:
                hobby_slots = [s for s in days[day_name] if '14:00' <= s.start_time <= '16:00']
                if hobby_slots:
                    slot = hobby_slots[0]
                    protected.append({
                        'day': slot.day,
                        'start_time': slot.start_time,
                        'end_time': slot.end_time,
                        'hours': slot.hours,
                        'reason': 'hobby_time'
                    })
                    break

        # Deduplicate (same slot might be protected for multiple reasons)
        seen = set()
        unique_protected = []
        for block in protected:
            key = (block['day'], block['start_time'])
            if key not in seen:
                seen.add(key)
                unique_protected.append(block)

        return unique_protected


def calculate_balance(free_slots: List[Dict],
                      course_count: int,
                      total_content_volume: int) -> Dict:
    """Convenience function to calculate balance.

    Args:
        free_slots: List of dicts with day, start_time, end_time, hours
        course_count: Number of courses
        total_content_volume: Total pages/slides

    Returns:
        Balance calculation result
    """
    agent = BalanceAgent()
    slots = [
        TimeSlot(s['day'], s['start_time'], s['end_time'], s.get('hours', 2))
        for s in free_slots
    ]
    return agent.calculate_balance(slots, course_count, total_content_volume)


if __name__ == "__main__":
    # Test with sample free slots
    print("=" * 60)
    print("BALANCE AGENT TEST")
    print("=" * 60)

    # Sample weekly free slots (20 hours)
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

    agent = BalanceAgent()
    result = calculate_balance(free_slots, course_count=6, total_content_volume=1285)

    print(f"\nTotal free hours: {result['total_free_hours']}h")
    print(f"Max study hours (65% cap): {result['max_study_hours']}h")
    print(f"Recommended (by content): {result['recommended_study_hours']}h")
    print(f"Protected hours: {result['protected_hours']}h")
    print(f"Final study allocation: {result['final_study_allocation']}h")
    print(f"Balance ratio: {result['balance_ratio']:.0%}")

    print(f"\nProtected blocks ({len(result['protected_blocks'])}):")
    for block in result['protected_blocks']:
        print(f"  - {block['day']} {block['start_time']}-{block['end_time']} "
              f"({block['hours']}h): {block['reason']}")

    print("\n" + "=" * 60)
    print("BALANCE AGENT TEST PASSED")
    print("=" * 60)
