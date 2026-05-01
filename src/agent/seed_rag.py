"""
Seed the RAG knowledge base with initial financial analysis content.

Usage:
    python -m src.agent.seed_rag
"""

import logging

from src.agent.rag_pipeline import get_rag_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Seed the ChromaDB with initial knowledge."""
    logger.info("🌱 Seeding RAG knowledge base...")
    
    try:
        rag = get_rag_pipeline()
        rag.seed_knowledge_base()
        logger.info("✅ Knowledge base seeded successfully")
        
        # Test retrieval
        test_query = "What is RSI?"
        results = rag.search(test_query, n_results=2)
        logger.info(f"📊 Test retrieval: Found {len(results['documents'])} documents")
        
        if results['documents']:
            logger.info(f"Sample: {results['documents'][0][:100]}...")
        
    except Exception as e:
        logger.error(f"❌ Failed to seed knowledge base: {e}")
        raise


if __name__ == "__main__":
    main()
