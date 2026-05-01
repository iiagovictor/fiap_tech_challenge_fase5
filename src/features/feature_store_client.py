"""
Client for interacting with Feast Feature Store.

Provides methods to retrieve features for online (real-time) and offline (batch) serving.
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from feast import FeatureStore

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FeastClient:
    """
    Wrapper around Feast FeatureStore for simplified feature retrieval.
    
    Usage:
        client = FeastClient()
        features = client.get_online_features(
            ticker="ITUB4.SA",
            timestamp=datetime.now()
        )
    """

    def __init__(self, repo_path: str | None = None):
        """
        Initialize Feast client.
        
        Args:
            repo_path: Path to Feast repository (default: from settings)
        """
        self.repo_path = repo_path or settings.feast_repo_path
        self.store = FeatureStore(repo_path=self.repo_path)
        logger.info(f"Initialized Feast Feature Store from {self.repo_path}")

    def get_online_features(
        self, ticker: str | list[str], timestamp: datetime | None = None
    ) -> pd.DataFrame:
        """
        Retrieve features from online store for real-time prediction.
        
        Args:
            ticker: Single ticker or list of tickers
            timestamp: Request timestamp (default: now)
        
        Returns:
            DataFrame with features for the requested entities
        """
        if isinstance(ticker, str):
            ticker = [ticker]

        if timestamp is None:
            timestamp = datetime.now()

        # Build entity dataframe
        entity_df = pd.DataFrame(
            {
                "ticker": ticker,
                "event_timestamp": [timestamp] * len(ticker),
            }
        )

        # Retrieve features using the feature service
        feature_vector = self.store.get_online_features(
            features=[
                "stock_technical_features:open",
                "stock_technical_features:high",
                "stock_technical_features:low",
                "stock_technical_features:close",
                "stock_technical_features:volume",
                "stock_technical_features:sma_5",
                "stock_technical_features:sma_10",
                "stock_technical_features:sma_20",
                "stock_technical_features:sma_50",
                "stock_technical_features:ema_12",
                "stock_technical_features:ema_26",
                "stock_technical_features:rsi_14",
                "stock_technical_features:macd",
                "stock_technical_features:macd_signal",
                "stock_technical_features:macd_histogram",
                "stock_technical_features:bb_upper",
                "stock_technical_features:bb_middle",
                "stock_technical_features:bb_lower",
                "stock_technical_features:bb_width",
                "stock_technical_features:atr_14",
                "stock_technical_features:obv",
                "stock_technical_features:volume_ma_20",
                "stock_technical_features:price_change",
                "stock_technical_features:price_change_5d",
            ],
            entity_rows=entity_df.to_dict(orient="records"),
        )

        # Convert to DataFrame
        df = feature_vector.to_df()

        logger.info(f"Retrieved online features for {len(ticker)} ticker(s)")
        return df

    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve historical features from offline store for batch training.
        
        Args:
            entity_df: DataFrame with columns ['ticker', 'event_timestamp']
            features: List of features to retrieve (default: all from service)
        
        Returns:
            DataFrame with historical features joined to entity_df
        """
        if features is None:
            # Use the feature service
            features = ["stock_prediction_service"]

        # Get historical features
        training_df = self.store.get_historical_features(
            entity_df=entity_df,
            features=features,
        ).to_df()

        logger.info(f"Retrieved {len(training_df)} rows of historical features")
        return training_df

    def materialize(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> None:
        """
        Materialize features to online store.
        
        This loads features from the offline store (Parquet) into Redis
        for low-latency online serving.
        
        Args:
            start_date: Start of materialization window
            end_date: End of materialization window (default: now)
        """
        if end_date is None:
            end_date = datetime.now()

        logger.info(
            f"Materializing features from {start_date} to {end_date} to online store..."
        )

        self.store.materialize(
            start_date=start_date,
            end_date=end_date,
        )

        logger.info("✅ Materialization complete")

    def get_feature_list(self) -> list[str]:
        """Get list of all available features in the feature store."""
        feature_views = self.store.list_feature_views()
        features = []
        for fv in feature_views:
            for feature in fv.features:
                features.append(f"{fv.name}:{feature.name}")
        return features


def get_feast_client() -> FeastClient:
    """Get Feast client instance."""
    return FeastClient()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize client
    client = get_feast_client()

    # List available features
    features = client.get_feature_list()
    print(f"\n✅ Available features ({len(features)}):")
    for f in features:
        print(f"  - {f}")
