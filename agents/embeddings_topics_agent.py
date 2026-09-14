"""Embeddings + Topic Summary Agent - Creates embeddings and topic summaries from course content."""

from typing import List, Dict, Optional
import re


class EmbeddingsTopicsAgent:
    """Converts processed course content into embeddings and topic summaries."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with a sentence-transformers model (local, free, offline).

        Args:
            model_name: Model name for sentence-transformers.
                       Default 'all-MiniLM-L6-v2' is fast and good quality.
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load model to avoid loading on import."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def process(self, slides: List[Dict], course_name: str = None) -> Dict:
        """Process slides into embeddings and topic summary.

        Args:
            slides: List of {slide_number, text, needs_vision} dicts
            course_name: Optional course name for metadata

        Returns:
            Dict with embeddings, topics, and metadata
        """
        # Filter slides with text content (skip vision-needed slides for now)
        text_slides = [s for s in slides if s.get('text') and not s.get('needs_vision')]

        if not text_slides:
            return {
                'course_name': course_name,
                'embeddings': [],
                'topics': [],
                'total_processed': 0,
                'vision_slides_count': len([s for s in slides if s.get('needs_vision')])
            }

        # Extract text
        texts = [s['text'] for s in text_slides]

        # Generate embeddings
        embeddings = self.model.encode(texts, show_progress_bar=False)

        # Generate topic summary from all text
        all_text = ' '.join(texts)
        topics = self._extract_topics(all_text)

        return {
            'course_name': course_name,
            'embeddings': embeddings.tolist(),
            'slide_numbers': [s['slide_number'] for s in text_slides],
            'topics': topics,
            'total_processed': len(text_slides),
            'vision_slides_count': len([s for s in slides if s.get('needs_vision')])
        }

    def _extract_topics(self, text: str, max_topics: int = 10) -> List[str]:
        """Extract main topics from text using simple keyword extraction.

        This is a lightweight approach - no LLM needed.
        For better results, use Gemini/Groq API.

        Args:
            text: Full text to analyze
            max_topics: Maximum number of topics to return

        Returns:
            List of topic strings
        """
        # Simple approach: extract capitalized phrases and common technical terms
        # This is a placeholder - the real implementation could use an LLM

        # Look for section headers (ALL CAPS or Title Case patterns)
        patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',  # Title Case
            r'\b([A-Z]{2,})\b',  # Acronyms
        ]

        candidates = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)

        # Filter and dedupe
        stop_words = {'The', 'This', 'That', 'These', 'Those', 'In', 'On', 'At', 'To', 'For',
                      'Of', 'And', 'Or', 'But', 'Is', 'Are', 'Was', 'Were', 'Be', 'Been',
                      'Being', 'Have', 'Has', 'Had', 'Do', 'Does', 'Did', 'Will', 'Would',
                      'Could', 'Should', 'May', 'Might', 'Must', 'Shall', 'Can', 'Need',
                      'Dare', 'Ought', 'Used', 'It', 'Its', 'They', 'We', 'You', 'He', 'She'}

        topics = []
        seen = set()
        for candidate in candidates:
            if candidate not in stop_words and len(candidate) > 2 and candidate not in seen:
                topics.append(candidate)
                seen.add(candidate)
                if len(topics) >= max_topics:
                    break

        return topics

    def process_batch(self, batch: Dict, course_name: str = None) -> Dict:
        """Process a single batch (convenience method).

        Args:
            batch: Dict with 'slides' key
            course_name: Optional course name

        Returns:
            Processing result
        """
        return self.process(batch['slides'], course_name)


def create_embeddings(slides: List[Dict], course_name: str = None, model_name: str = None) -> Dict:
    """Convenience function to create embeddings from slides.

    Args:
        slides: List of slide dicts
        course_name: Optional course name
        model_name: Optional model name override

    Returns:
        Dict with embeddings and topics
    """
    agent = EmbeddingsTopicsAgent(model_name or "all-MiniLM-L6-v2")
    return agent.process(slides, course_name)


if __name__ == "__main__":
    # Quick test with sample data
    import sys

    sample_slides = [
        {'slide_number': 1, 'text': 'Introduction to Machine Learning and AI fundamentals', 'needs_vision': False},
        {'slide_number': 2, 'text': 'Supervised learning uses labeled data for training models', 'needs_vision': False},
        {'slide_number': 3, 'text': 'Neural networks are inspired by biological neurons', 'needs_vision': False},
    ]

    agent = EmbeddingsTopicsAgent()
    result = agent.process(sample_slides, "Sample Course")

    print(f"Course: {result['course_name']}")
    print(f"Slides processed: {result['total_processed']}")
    print(f"Embedding dimension: {len(result['embeddings'][0]) if result['embeddings'] else 0}")
    print(f"Topics: {result['topics']}")
