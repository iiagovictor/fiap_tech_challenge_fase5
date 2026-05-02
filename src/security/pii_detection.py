"""
PII (Personally Identifiable Information) detection using Presidio.

Detects and redacts sensitive information from text:
- Email addresses
- Phone numbers
- Credit card numbers
- Names
- Addresses
"""

import logging

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

logger = logging.getLogger(__name__)


class PIIDetector:
    """
    PII detector using Microsoft Presidio.

    Detects and optionally redacts PII from text.
    """

    def __init__(self, languages: list[str] | None = None) -> None:
        """
        Initialize PII detector.

        Args:
            languages: List of languages to support (default: ["en", "pt"])
        """
        self.languages = languages or ["en", "pt"]
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        logger.info(f"Initialized PII detector for languages: {self.languages}")

    def detect(self, text: str, language: str = "en") -> list[dict]:
        """
        Detect PII in text.

        Args:
            text: Input text to analyze
            language: Language code (en, pt, etc.)

        Returns:
            List of detected PII entities with type, score, and location
        """
        if not text or not text.strip():
            return []

        try:
            results = self.analyzer.analyze(
                text=text,
                language=language,
                entities=None,  # Detect all entity types
            )

            detected = []
            for result in results:
                detected.append(
                    {
                        "type": result.entity_type,
                        "start": result.start,
                        "end": result.end,
                        "score": result.score,
                        "text": text[result.start : result.end],
                    }
                )

            if detected:
                logger.warning(f"Detected {len(detected)} PII entities in text")

            return detected

        except Exception as e:
            logger.error(f"PII detection failed: {e}")
            return []

    def anonymize(self, text: str, language: str = "en") -> str:
        """
        Anonymize PII in text by replacing with placeholders.

        Args:
            text: Input text
            language: Language code

        Returns:
            Anonymized text with PII replaced by placeholders
        """
        if not text or not text.strip():
            return text

        try:
            # Detect PII
            results = self.analyzer.analyze(text=text, language=language)

            if not results:
                return text

            # Anonymize
            anonymized_result = self.anonymizer.anonymize(text=text, analyzer_results=results)

            logger.info(f"Anonymized {len(results)} PII entities")
            return anonymized_result.text

        except Exception as e:
            logger.error(f"Anonymization failed: {e}")
            return text

    def has_pii(self, text: str, language: str = "en", threshold: float = 0.5) -> bool:
        """
        Check if text contains PII above confidence threshold.

        Args:
            text: Input text
            language: Language code
            threshold: Minimum confidence score (0-1)

        Returns:
            True if PII detected above threshold
        """
        detected = self.detect(text, language)
        return any(item["score"] >= threshold for item in detected)


# Global instance
_pii_detector = None


def get_pii_detector() -> PIIDetector:
    """Get singleton PII detector instance."""
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Test PII detection
    detector = get_pii_detector()

    # Test cases
    test_texts = [
        "My email is john.doe@example.com and phone is 555-1234",
        "Contact me at maria.silva@empresa.com.br or +55 11 98765-4321",
        "The stock price is $45.50 and volume is 1,000,000 shares",
    ]

    print("\n🔍 Testing PII Detection\n")
    for i, text in enumerate(test_texts, 1):
        print(f"Test {i}: {text}")
        detected = detector.detect(text)
        if detected:
            print(f"  Detected: {detected}")
            anonymized = detector.anonymize(text)
            print(f"  Anonymized: {anonymized}")
        else:
            print("  No PII detected")
        print()
