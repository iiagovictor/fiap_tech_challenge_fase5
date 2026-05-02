"""
MLP (Multi-Layer Perceptron) baseline model implemented in PyTorch.

Used as a complementary baseline for comparison against the LSTM model.
Requires: pip install torch  (or pip install -e ".[torch]")
"""

import logging

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PyTorch model definition
# ---------------------------------------------------------------------------


def _build_mlp(input_dim: int, hidden_dims: list[int], dropout: float):  # noqa: ANN202
    """Build a Sequential MLP with ReLU activations and Dropout."""
    try:
        import torch.nn as nn
    except ImportError as exc:
        raise ImportError(
            "PyTorch is required for MLPClassifier. " "Install it with: pip install torch"
        ) from exc

    layers: list[nn.Module] = []
    in_dim = input_dim
    for h in hidden_dims:
        layers += [nn.Linear(in_dim, h), nn.ReLU(), nn.Dropout(dropout)]
        in_dim = h
    layers.append(nn.Linear(in_dim, 1))
    layers.append(nn.Sigmoid())
    return nn.Sequential(*layers)


class MLPClassifier:
    """
    Scikit-learn–style wrapper around a PyTorch MLP for binary classification.

    Usage::

        clf = MLPClassifier(input_dim=24, hidden_dims=[64, 32], dropout=0.3)
        clf.fit(x_train, y_train, epochs=50, batch_size=64)
        metrics = clf.evaluate(x_test, y_test)
        proba  = clf.predict_proba(x_test)

    Parameters
    ----------
    input_dim : int
        Number of input features.
    hidden_dims : list[int]
        Sizes of hidden layers (default: [128, 64, 32]).
    dropout : float
        Dropout probability applied after each hidden layer (default: 0.3).
    lr : float
        Adam learning rate (default: 1e-3).
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.3,
        lr: float = 1e-3,
    ) -> None:
        try:
            import torch
            import torch.nn as nn
        except ImportError as exc:
            raise ImportError(
                "PyTorch is required for MLPClassifier. " "Install it with: pip install torch"
            ) from exc

        self._torch = torch
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims or [128, 64, 32]
        self.dropout = dropout
        self.lr = lr

        self.model = _build_mlp(input_dim, self.hidden_dims, dropout)
        self.criterion = nn.BCELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.history: dict[str, list[float]] = {"loss": [], "val_loss": []}

    # ------------------------------------------------------------------
    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        epochs: int = 50,
        batch_size: int = 64,
        x_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        verbose: bool = True,
    ) -> "MLPClassifier":
        """Train the MLP.

        Args:
            x_train: Training features, shape (n, input_dim).
            y_train: Binary labels, shape (n,).
            epochs:  Number of training epochs.
            batch_size: Mini-batch size.
            x_val: Optional validation features.
            y_val: Optional validation labels.
            verbose: Log epoch summary when True.

        Returns:
            self
        """
        torch = self._torch
        x_t = torch.tensor(x_train, dtype=torch.float32)
        y_t = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)

        dataset = torch.utils.data.TensorDataset(x_t, y_t)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        self.model.train()
        for epoch in range(1, epochs + 1):
            epoch_loss = 0.0
            for x_batch, y_batch in loader:
                self.optimizer.zero_grad()
                preds = self.model(x_batch)
                loss = self.criterion(preds, y_batch)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item() * len(x_batch)

            epoch_loss /= len(x_t)
            self.history["loss"].append(epoch_loss)

            val_loss_value = float("nan")
            if x_val is not None and y_val is not None:
                val_loss_value = self._val_loss(x_val, y_val)
                self.history["val_loss"].append(val_loss_value)

            if verbose and (epoch % 10 == 0 or epoch == 1):
                msg = f"Epoch {epoch:3d}/{epochs} — loss: {epoch_loss:.4f}"
                if not np.isnan(val_loss_value):
                    msg += f"  val_loss: {val_loss_value:.4f}"
                logger.info(msg)

        return self

    def _val_loss(self, x_val: np.ndarray, y_val: np.ndarray) -> float:
        torch = self._torch
        self.model.eval()
        with torch.no_grad():
            x_t = torch.tensor(x_val, dtype=torch.float32)
            y_t = torch.tensor(y_val, dtype=torch.float32).unsqueeze(1)
            preds = self.model(x_t)
            loss = self.criterion(preds, y_t).item()
        self.model.train()
        return loss

    # ------------------------------------------------------------------
    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return predicted probabilities for the positive class."""
        torch = self._torch
        self.model.eval()
        with torch.no_grad():
            x_t = torch.tensor(x, dtype=torch.float32)
            proba = self.model(x_t).squeeze(1).numpy()
        return proba

    def predict(self, x: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        """Return binary class predictions."""
        return (self.predict_proba(x) >= threshold).astype(int)

    # ------------------------------------------------------------------
    def evaluate(self, x_test: np.ndarray, y_test: np.ndarray) -> dict[str, float]:
        """Compute classification metrics on a test set."""
        y_proba = self.predict_proba(x_test)
        y_pred = (y_proba >= 0.5).astype(int)

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_proba)),
        }

        logger.info("MLP Test Metrics:")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v:.4f}")

        return metrics


# ---------------------------------------------------------------------------
# High-level training function (mirrors baseline.py API)
# ---------------------------------------------------------------------------


def train_mlp_baseline(
    features_path: str = "features/stock_features.parquet",
    hidden_dims: list[int] | None = None,
    dropout: float = 0.3,
    lr: float = 1e-3,
    epochs: int = 50,
    batch_size: int = 64,
) -> dict[str, float]:
    """
    Train the MLP PyTorch baseline and return test metrics.

    Loads features from storage, scales them, trains the MLP, and evaluates
    it on a held-out test set.  Designed to be called from the Makefile target
    ``make train-mlp`` or from the training pipeline.

    Args:
        features_path: Path inside storage to the Parquet feature file.
        hidden_dims: Hidden layer sizes (default: [128, 64, 32]).
        dropout: Dropout rate (default: 0.3).
        lr: Adam learning rate (default: 1e-3).
        epochs: Training epochs (default: 50).
        batch_size: Mini-batch size (default: 64).

    Returns:
        Dictionary with accuracy, precision, recall, f1_score, roc_auc.
    """
    from src.config.storage import get_storage

    storage = get_storage()
    logger.info("Loading training data for MLP baseline...")
    df = storage.read_parquet(features_path)

    exclude_cols = ["date", "ticker", "target"]
    numeric_dtypes = [np.float64, np.float32, np.int64]
    feature_cols = [
        c for c in df.columns if c not in exclude_cols and df[c].dtype in numeric_dtypes
    ]

    x = df[feature_cols].values.astype(np.float32)
    y = df["target"].values.astype(np.float32)

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )
    x_train, x_val, y_train, y_val = train_test_split(
        x_train, y_train, test_size=0.2, random_state=42, stratify=y_train
    )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train).astype(np.float32)
    x_val = scaler.transform(x_val).astype(np.float32)
    x_test = scaler.transform(x_test).astype(np.float32)

    logger.info(f"Train: {len(x_train)} | Val: {len(x_val)} | Test: {len(x_test)}")

    clf = MLPClassifier(
        input_dim=x_train.shape[1],
        hidden_dims=hidden_dims or [128, 64, 32],
        dropout=dropout,
        lr=lr,
    )
    clf.fit(x_train, y_train, epochs=epochs, batch_size=batch_size, x_val=x_val, y_val=y_val)

    metrics = clf.evaluate(x_test, y_test)
    logger.info("✅ MLP PyTorch baseline training complete")
    return metrics


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    results = train_mlp_baseline()
    print("\n📊 MLP PyTorch Baseline Results:")
    for k, v in results.items():
        print(f"  {k}: {v:.4f}")
