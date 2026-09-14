"""Tests for Batch Ingestion Agent."""

import pytest
import sys
from pathlib import Path

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from batch_ingestion_agent import BatchIngestionAgent, ingest_course


class TestBatchIngestionAgent:
    """Test suite for Batch Ingestion Agent."""

    def test_needs_vision_text_heavy(self):
        """Slides with >= 20 words should NOT need vision."""
        agent = BatchIngestionAgent()
        # Exactly 20 words
        text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
        assert agent._needs_vision(text) is False

    def test_needs_vision_text_light(self):
        """Slides with < 20 words SHOULD need vision."""
        agent = BatchIngestionAgent()
        text = "Only few words"
        assert agent._needs_vision(text) is True

    def test_needs_vision_empty(self):
        """Empty slides should need vision."""
        agent = BatchIngestionAgent()
        assert agent._needs_vision("") is True

    def test_create_batches_correct_size(self):
        """Batches should be split according to batch_size."""
        agent = BatchIngestionAgent(batch_size=3)
        slides = [{'slide_number': i, 'text': f'Slide {i}', 'needs_vision': False}
                  for i in range(1, 8)]  # 7 slides

        batches = agent._create_batches(slides)

        assert len(batches) == 3  # 3+3+1
        assert batches[0]['total_slides'] == 3
        assert batches[1]['total_slides'] == 3
        assert batches[2]['total_slides'] == 1

    def test_extract_course_name(self):
        """Course name extraction should clean filenames."""
        agent = BatchIngestionAgent()
        assert agent._extract_course_name("Computer_vision_cours") == "Computer vision cours"
        assert agent._extract_course_name("MLOps-for-IoT") == "MLOps for IoT"


# Integration tests with real course files
@pytest.fixture
def periode1_path():
    """Path to Periode-1 courses."""
    return Path(r"C:\study-agent-planner\Periode-1")


class TestRealCourses:
    """Integration tests with actual course files."""

    def test_fintech_pdf(self, periode1_path):
        """Test Fintech course PDF (small, 9 pages)."""
        fintech_path = periode1_path / "Fintech" / "Cours" / "Support de cours_241018_070457.pdf"

        if not fintech_path.exists():
            pytest.skip(f"Fintech PDF not found: {fintech_path}")

        result = ingest_course(str(fintech_path))

        assert result['total_slides'] > 0
        assert len(result['batches']) >= 1
        assert 'course_name' in result

        print(f"\n[OK] Fintech: {result['total_slides']} pages, "
              f"{result['vision_needed_count']} need vision, "
              f"{len(result['batches'])} batch(es)")

    def test_computer_vision_pdf(self, periode1_path):
        """Test Computer Vision course PDF (large, ~290 slides)."""
        cv_path = periode1_path / "Computer vision et applications" / "Cours" / "Computer_vision_cours_AIM_sep2024.pdf"

        if not cv_path.exists():
            pytest.skip(f"Computer Vision PDF not found: {cv_path}")

        result = ingest_course(str(cv_path))

        assert result['total_slides'] > 100  # Should be ~290
        assert len(result['batches']) > 5  # Should be ~10-12 batches

        print(f"\n[OK] Computer Vision: {result['total_slides']} slides, "
              f"{result['vision_needed_count']} need vision, "
              f"{len(result['batches'])} batches")

    def test_wot_pdfs(self, periode1_path):
        """Test Web of Things PDFs."""
        wot_path = periode1_path / "Fondements du Web of Things" / "Cours"

        if not wot_path.exists():
            pytest.skip(f"WoT path not found: {wot_path}")

        pdf_files = list(wot_path.glob("*.pdf"))
        if not pdf_files:
            pytest.skip("No WoT PDFs found")

        total_slides = 0
        for pdf in pdf_files[:2]:  # Test first 2 only
            result = ingest_course(str(pdf))
            total_slides += result['total_slides']
            print(f"\n[OK] WoT ({pdf.name}): {result['total_slides']} pages")

        assert total_slides > 0

    def test_mlops_pdfs(self, periode1_path):
        """Test MLOps PDFs."""
        mlops_path = periode1_path / "MLOps for IoT Edges" / "Cours"

        if not mlops_path.exists():
            pytest.skip(f"MLOps path not found: {mlops_path}")

        pdf_files = list(mlops_path.glob("*.pdf"))
        pdf_files = [f for f in pdf_files if "Design Patterns" not in f.name]  # Skip large book

        if not pdf_files:
            pytest.skip("No MLOps PDFs found")

        for pdf in pdf_files[:2]:  # Test first 2
            result = ingest_course(str(pdf))
            print(f"\n[OK] MLOps ({pdf.name}): {result['total_slides']} pages, "
                  f"{result['vision_needed_count']} need vision")


def test_summary():
    """Print summary of all courses."""
    periode1 = Path(r"C:\study-agent-planner\Periode-1")

    if not periode1.exists():
        pytest.skip("Periode-1 folder not found")

    print("\n" + "="*60)
    print("BATCH INGESTION SUMMARY")
    print("="*60)

    agent = BatchIngestionAgent()

    # Map of courses to their cours folders
    courses = {
        "Computer Vision": periode1 / "Computer vision et applications" / "Cours",
        "Web of Things": periode1 / "Fondements du Web of Things" / "Cours",
        "MLOps": periode1 / "MLOps for IoT Edges" / "Cours",
        "Geo/Spatial": periode1 / "Données spatiale_ traitement, analyse et applications" / "Cours",
        "Fintech": periode1 / "Fintech" / "Cours",
        "Machine Learning": periode1 / "Machine Learning & bases massives MM",
    }

    for course_name, path in courses.items():
        if not path.exists():
            continue

        pdfs = list(path.glob("**/*.pdf"))
        if not pdfs:
            continue

        total = 0
        vision = 0
        for pdf in pdfs:
            try:
                r = agent.ingest(str(pdf))
                total += r['total_slides']
                vision += r['vision_needed_count']
            except Exception as e:
                print(f"  Error with {pdf.name}: {e}")

        batches = (total + agent.batch_size - 1) // agent.batch_size
        print(f"{course_name:20} | {total:4} pages | {vision:4} need vision | {batches:3} batches")

    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
