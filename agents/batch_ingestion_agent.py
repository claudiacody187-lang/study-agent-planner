"""Batch Ingestion Agent - Splits large slide decks into batches and routes to text/vision processing."""

import fitz  # PyMuPDF
from pptx import Presentation
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re


class BatchIngestionAgent:
    """Processes large PDF/PPTX files by splitting into batches and routing to appropriate extractors."""

    BATCH_SIZE = 25  # slides per batch
    MIN_TEXT_WORDS = 20  # threshold for vision model routing

    def __init__(self, batch_size: int = None):
        self.batch_size = batch_size or self.BATCH_SIZE

    def ingest(self, file_path: str) -> Dict:
        """Main entry point - processes a PDF or PPTX file.

        Args:
            file_path: Path to PDF or PPTX file

        Returns:
            Dict with 'batches', 'total_slides', 'vision_needed_count', 'course_name'
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext == '.pdf':
            slides = self._extract_pdf(file_path)
        elif ext == '.pptx':
            slides = self._extract_pptx(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")

        # Route slides to text or vision processing
        for slide in slides:
            slide['needs_vision'] = self._needs_vision(slide['text'])

        # Split into batches
        batches = self._create_batches(slides)

        return {
            'course_name': self._extract_course_name(path.stem),
            'total_slides': len(slides),
            'vision_needed_count': sum(1 for s in slides if s['needs_vision']),
            'batches': batches
        }

    def _extract_pdf(self, file_path: str) -> List[Dict]:
        """Extract text from PDF, one dict per page."""
        slides = []
        with fitz.open(file_path) as doc:
            for i, page in enumerate(doc, 1):
                text = page.get_text("text").strip()
                # Clean up PDF text
                text = re.sub(r'\s+', ' ', text)
                slides.append({
                    'slide_number': i,
                    'text': text,
                    'needs_vision': False
                })
        return slides

    def _extract_pptx(self, file_path: str) -> List[Dict]:
        """Extract text from PPTX, one dict per slide."""
        slides = []
        prs = Presentation(file_path)
        for i, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    texts.append(shape.text.strip())
            text = ' '.join(texts)
            text = re.sub(r'\s+', ' ', text).strip()
            slides.append({
                'slide_number': i,
                'text': text,
                'needs_vision': False
            })
        return slides

    def _needs_vision(self, text: str) -> bool:
        """Determine if slide needs vision model (image-heavy or text-light)."""
        word_count = len(text.split())
        return word_count < self.MIN_TEXT_WORDS

    def _create_batches(self, slides: List[Dict]) -> List[Dict]:
        """Split slides into batches for processing."""
        batches = []
        for i in range(0, len(slides), self.batch_size):
            batch_slides = slides[i:i + self.batch_size]
            batches.append({
                'batch_number': len(batches) + 1,
                'slides': batch_slides,
                'total_slides': len(batch_slides)
            })
        return batches

    def _extract_course_name(self, filename: str) -> str:
        """Extract a clean course name from filename."""
        # Remove common suffixes and clean up
        name = re.sub(r'[_-]', ' ', filename)
        name = re.sub(r'\s+', ' ', name).strip()
        return name


def ingest_course(course_path: str, batch_size: int = None) -> Dict:
    """Convenience function to ingest a course file.

    Args:
        course_path: Path to PDF or PPTX file
        batch_size: Optional custom batch size

    Returns:
        Ingestion result dict
    """
    agent = BatchIngestionAgent(batch_size)
    return agent.ingest(course_path)


if __name__ == "__main__":
    # Quick test with a sample file
    import sys
    if len(sys.argv) > 1:
        result = ingest_course(sys.argv[1])
        print(f"Course: {result['course_name']}")
        print(f"Total slides: {result['total_slides']}")
        print(f"Vision needed: {result['vision_needed_count']}")
        print(f"Batches: {len(result['batches'])}")
    else:
        print("Usage: python batch_ingestion_agent.py <file_path>")
