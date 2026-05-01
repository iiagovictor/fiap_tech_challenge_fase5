"""
RAG (Retrieval Augmented Generation) pipeline using ChromaDB.

Provides:
- Document ingestion and embedding
- Semantic search over market knowledge
- Context retrieval for LLM queries
"""

import logging
from typing import Any

import chromadb
from chromadb.config import Settings

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGPipeline:
    """
    RAG pipeline for retrieving relevant market knowledge.
    
    Uses ChromaDB for vector storage and retrieval.
    """

    def __init__(
        self,
        collection_name: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            collection_name: ChromaDB collection name
            host: ChromaDB host
            port: ChromaDB port
        """
        self.collection_name = collection_name or settings.chroma_collection
        self.host = host or settings.chroma_host
        self.port = port or settings.chroma_port

        # Disable telemetry completely to avoid PostHog errors
        import os
        os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
        os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"

        # Initialize ChromaDB client
        self.client = chromadb.HttpClient(
            host=self.host,
            port=self.port,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Market knowledge base for stock analysis"},
            )
            logger.info(f"Connected to ChromaDB collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            self.collection = None

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """
        Add documents to the knowledge base.
        
        Args:
            documents: List of text documents
            metadatas: Optional metadata for each document
            ids: Optional IDs for each document (auto-generated if not provided)
        """
        if self.collection is None:
            logger.error("Collection not initialized")
            return

        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]

        if metadatas is None:
            metadatas = [{}] * len(documents)

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"Added {len(documents)} documents to collection")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: dict | None = None,
    ) -> dict:
        """
        Search for relevant documents.
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
        
        Returns:
            Dictionary with documents, metadatas, distances
        """
        if self.collection is None:
            logger.error("Collection not initialized")
            return {"documents": [], "metadatas": [], "distances": []}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata,
            )

            logger.info(f"Retrieved {len(results['documents'][0])} documents for query")

            return {
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"documents": [], "metadatas": [], "distances": []}

    def retrieve_context(self, query: str, n_results: int = 3) -> str:
        """
        Retrieve context for a query as formatted text.
        
        Args:
            query: Search query
            n_results: Number of documents to retrieve
        
        Returns:
            Formatted context string
        """
        results = self.search(query, n_results=n_results)

        if not results["documents"]:
            return "No relevant context found."

        context_parts = []
        for i, doc in enumerate(results["documents"]):
            context_parts.append(f"[Source {i+1}]\n{doc}\n")

        return "\n".join(context_parts)

    def seed_knowledge_base(self) -> None:
        """Seed the knowledge base with initial financial analysis content."""
        documents = [
            "RSI (Relative Strength Index) is a momentum indicator that measures the speed and magnitude of price changes. Values above 70 indicate overbought conditions, while values below 30 suggest oversold conditions.",
            "MACD (Moving Average Convergence Divergence) is a trend-following momentum indicator that shows the relationship between two moving averages. When MACD crosses above the signal line, it suggests a bullish signal.",
            "Bollinger Bands consist of a middle band (SMA) and two outer bands (standard deviations). When price touches the upper band, the stock may be overbought; touching the lower band may indicate oversold conditions.",
            "Moving averages smooth out price data to identify trends. A golden cross occurs when a short-term MA crosses above a long-term MA, signaling potential upward momentum.",
            "Volume analysis is crucial for confirming price movements. Increasing volume during an uptrend validates the strength of the movement.",
            "Support and resistance levels are price points where stocks tend to reverse direction. Breaking through resistance can signal continued upward movement.",
            "Brazilian stock market (B3) operates with stocks ending in .SA suffix. IBOVESPA (^BVSP) is the main index tracking the most traded stocks.",
            "Bank stocks like ITUB4 (Itaú) and BBDC4 (Bradesco) are influenced by interest rates, economic growth, and credit quality.",
            "Commodity-related stocks like VALE3 (Vale - mining) and PETR4 (Petrobras - oil) are affected by global commodity prices and currency fluctuations.",
        ]

        metadatas = [
            {"category": "technical_analysis", "indicator": "RSI"},
            {"category": "technical_analysis", "indicator": "MACD"},
            {"category": "technical_analysis", "indicator": "Bollinger_Bands"},
            {"category": "technical_analysis", "indicator": "Moving_Averages"},
            {"category": "technical_analysis", "indicator": "Volume"},
            {"category": "technical_analysis", "concept": "Support_Resistance"},
            {"category": "market_info", "market": "Brazilian"},
            {"category": "market_info", "sector": "Banking"},
            {"category": "market_info", "sector": "Commodities"},
        ]

        ids = [f"seed_{i}" for i in range(len(documents))]

        self.add_documents(documents, metadatas, ids)
        logger.info("✅ Knowledge base seeded with initial content")


def get_rag_pipeline() -> RAGPipeline:
    """Get RAG pipeline instance."""
    return RAGPipeline()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Test RAG pipeline
    rag = get_rag_pipeline()

    # Seed knowledge base
    print("\n📚 Seeding knowledge base...")
    rag.seed_knowledge_base()

    # Test search
    print("\n🔍 Testing search...")
    query = "What does RSI indicate about a stock?"
    context = rag.retrieve_context(query, n_results=2)
    print(f"\nQuery: {query}")
    print(f"\nRetrieved Context:\n{context}")
