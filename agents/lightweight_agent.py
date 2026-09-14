"""Lightweight Agent - Single-pass processing for small documents and module lists."""

from typing import List, Dict, Optional
from pathlib import Path
import fitz  # PyMuPDF


class LightweightAgent:
    """Processes small documents in a single pass without chunking."""

    # Threshold for "lightweight" (pages)
    LIGHTWEIGHT_THRESHOLD = 50

    def __init__(self, threshold: int = None):
        self.threshold = threshold or self.LIGHTWEIGHT_THRESHOLD

    def process_pdf(self, file_path: str, course_name: str = None) -> Dict:
        """Process a small PDF in one pass.

        Args:
            file_path: Path to PDF file
            course_name: Optional course name

        Returns:
            Dict with extracted content
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with fitz.open(file_path) as doc:
            page_count = len(doc)

            # Check if actually lightweight
            if page_count > self.threshold:
                print(f"Warning: {page_count} pages exceeds threshold {self.threshold}")

            # Extract all text in one pass
            all_text = []
            for i, page in enumerate(doc, 1):
                text = page.get_text("text").strip()
                all_text.append({
                    'page_number': i,
                    'text': text
                })

        return {
            'course_name': course_name or path.stem,
            'type': 'pdf',
            'total_pages': page_count,
            'is_lightweight': page_count <= self.threshold,
            'content': all_text
        }

    def process_module_list(self, modules: List[str], course_name: str) -> Dict:
        """Process a list of module titles (e.g., AWS modules).

        Args:
            modules: List of module names/titles
            course_name: Course name

        Returns:
            Dict with module list
        """
        return {
            'course_name': course_name,
            'type': 'module_list',
            'total_modules': len(modules),
            'is_lightweight': True,
            'content': [
                {'module_number': i, 'title': title}
                for i, title in enumerate(modules, 1)
            ]
        }

    def process(self, input_data: Dict) -> Dict:
        """Process based on input type.

        Args:
            input_data: Dict with 'type' ('pdf' or 'module_list') and relevant data

        Returns:
            Processing result
        """
        if input_data['type'] == 'pdf':
            return self.process_pdf(input_data['path'], input_data.get('course_name'))
        elif input_data['type'] == 'module_list':
            return self.process_module_list(input_data['modules'], input_data.get('course_name'))
        else:
            raise ValueError(f"Unknown type: {input_data['type']}")


def process_lightweight(file_path: str = None, modules: List[str] = None, course_name: str = None) -> Dict:
    """Convenience function to process lightweight content.

    Args:
        file_path: Path to PDF (optional)
        modules: List of module titles (optional)
        course_name: Course name

    Returns:
        Processing result
    """
    agent = LightweightAgent()

    if file_path:
        return agent.process_pdf(file_path, course_name)
    elif modules:
        return agent.process_module_list(modules, course_name)
    else:
        raise ValueError("Must provide either file_path or modules")


if __name__ == "__main__":
    # Test with Fintech PDF
    import sys

    fintech_path = r"C:\study-agent-planner\Periode-1\Fintech\Cours\Support de cours_241018_070457.pdf"

    agent = LightweightAgent()

    print("=" * 60)
    print("LIGHTWEIGHT AGENT TEST")
    print("=" * 60)

    # Test 1: Fintech PDF (9 pages)
    print("\n[1] Processing Fintech PDF...")
    result = agent.process_pdf(fintech_path, "Fintech")
    print(f"    Course: {result['course_name']}")
    print(f"    Pages: {result['total_pages']}")
    print(f"    Is lightweight: {result['is_lightweight']}")

    # Test 2: AWS Module list
    print("\n[2] Processing AWS Module list...")
    aws_modules = [
        "Module 1: Introduction to Machine Learning",
        "Module 2: Data Preparation",
        "Module 3: Model Training",
        "Module 4: Model Evaluation",
        "Module 5: Feature Engineering",
        "Module 6: Model Deployment",
        "Module 7: MLOps Fundamentals",
        "Module 8: Model Monitoring",
        "Module 9: Advanced ML Techniques",
        "Module 10: SageMaker Overview",
        "Module 11: AutoML",
        "Module 12: Final Project"
    ]

    result = agent.process_module_list(aws_modules, "Machine Learning - AWS")
    print(f"    Course: {result['course_name']}")
    print(f"    Modules: {result['total_modules']}")
    print(f"    Type: {result['type']}")

    print("\n" + "=" * 60)
    print("LIGHTWEIGHT AGENT TEST PASSED")
    print("=" * 60)
