"""
Cloud-agnostic storage abstraction using fsspec.

Supports local, S3, GCS, and Azure Blob Storage transparently.
All read/write operations use fsspec under the hood, allowing seamless
switching between storage backends via configuration.
"""

import json
from pathlib import Path
from typing import Any

import fsspec
import joblib
import pandas as pd

from src.config.settings import get_settings

settings = get_settings()


class StorageClient:
    """
    Unified storage interface for local and cloud storage.
    
    Automatically configures the appropriate fsspec filesystem based on
    settings.storage_backend.
    
    Usage:
        storage = StorageClient()
        storage.write_parquet(df, "features/stock_features.parquet")
        df = storage.read_parquet("features/stock_features.parquet")
    """

    def __init__(self):
        self.backend = settings.storage_backend
        self.base_uri = settings.storage_uri.rstrip("/")
        self.fs = self._get_filesystem()

    def _get_filesystem(self) -> fsspec.AbstractFileSystem:
        """Initialize the appropriate fsspec filesystem."""
        if self.backend == "local":
            return fsspec.filesystem("file")

        elif self.backend == "s3":
            storage_options = {
                "anon": False,
                "key": settings.aws_access_key_id,
                "secret": settings.aws_secret_access_key,
            }
            if settings.aws_endpoint_url:
                storage_options["client_kwargs"] = {
                    "endpoint_url": settings.aws_endpoint_url
                }
            return fsspec.filesystem("s3", **storage_options)

        elif self.backend == "gcs":
            # For GCS, credentials are typically loaded from env (GOOGLE_APPLICATION_CREDENTIALS)
            return fsspec.filesystem("gcs")

        elif self.backend == "azure":
            # Azure credentials from env (AZURE_STORAGE_CONNECTION_STRING or account_name/account_key)
            return fsspec.filesystem("az")

        else:
            raise ValueError(f"Unsupported storage backend: {self.backend}")

    def _full_path(self, path: str) -> str:
        """Construct full path by combining base_uri with relative path."""
        path = path.lstrip("/")
        return f"{self.base_uri}/{path}"

    # ============================================================
    # Generic read/write
    # ============================================================
    def read_bytes(self, path: str) -> bytes:
        """Read raw bytes from storage."""
        full_path = self._full_path(path)
        with self.fs.open(full_path, "rb") as f:
            return f.read()

    def write_bytes(self, data: bytes, path: str) -> None:
        """Write raw bytes to storage."""
        full_path = self._full_path(path)
        # Ensure parent directory exists (fsspec handles this gracefully)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        with self.fs.open(full_path, "wb") as f:
            f.write(data)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """Read text file from storage."""
        full_path = self._full_path(path)
        with self.fs.open(full_path, "r", encoding=encoding) as f:
            return f.read()

    def write_text(self, text: str, path: str, encoding: str = "utf-8") -> None:
        """Write text file to storage."""
        full_path = self._full_path(path)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        with self.fs.open(full_path, "w", encoding=encoding) as f:
            f.write(text)

    # ============================================================
    # Structured data formats
    # ============================================================
    def read_parquet(self, path: str) -> pd.DataFrame:
        """Read Parquet file into DataFrame."""
        full_path = self._full_path(path)
        return pd.read_parquet(full_path, filesystem=self.fs)

    def write_parquet(self, df: pd.DataFrame, path: str) -> None:
        """Write DataFrame to Parquet format."""
        full_path = self._full_path(path)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        df.to_parquet(full_path, filesystem=self.fs, index=False)

    def read_csv(self, path: str, **kwargs) -> pd.DataFrame:
        """Read CSV file into DataFrame."""
        full_path = self._full_path(path)
        with self.fs.open(full_path, "r") as f:
            return pd.read_csv(f, **kwargs)

    def write_csv(self, df: pd.DataFrame, path: str, **kwargs) -> None:
        """Write DataFrame to CSV format."""
        full_path = self._full_path(path)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        with self.fs.open(full_path, "w") as f:
            df.to_csv(f, index=False, **kwargs)

    def read_json(self, path: str) -> Any:
        """Read JSON file."""
        full_path = self._full_path(path)
        with self.fs.open(full_path, "r") as f:
            return json.load(f)

    def write_json(self, obj: Any, path: str, indent: int = 2) -> None:
        """Write object to JSON file."""
        full_path = self._full_path(path)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        with self.fs.open(full_path, "w") as f:
            json.dump(obj, f, indent=indent)

    # ============================================================
    # ML artifacts (joblib, Keras models)
    # ============================================================
    def read_joblib(self, path: str) -> Any:
        """Load object serialized with joblib."""
        full_path = self._full_path(path)
        with self.fs.open(full_path, "rb") as f:
            return joblib.load(f)

    def write_joblib(self, obj: Any, path: str) -> None:
        """Save object with joblib."""
        full_path = self._full_path(path)
        self.fs.makedirs(self.fs._parent(full_path), exist_ok=True)
        with self.fs.open(full_path, "wb") as f:
            joblib.dump(obj, f)

    def read_keras_model(self, path: str):
        """
        Load Keras model from storage.
        
        Note: For cloud storage, downloads to temp file first since
        Keras load_model() doesn't support file-like objects directly.
        """
        from tensorflow import keras

        if self.backend == "local":
            full_path = self._full_path(path)
            return keras.models.load_model(full_path)
        else:
            # For cloud storage, download to temp file
            import tempfile

            data = self.read_bytes(path)
            with tempfile.NamedTemporaryFile(suffix=".keras", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            model = keras.models.load_model(tmp_path)
            Path(tmp_path).unlink()  # Clean up temp file
            return model

    def write_keras_model(self, model, path: str) -> None:
        """
        Save Keras model to storage.
        
        For cloud storage, saves to temp file first then uploads.
        """
        if self.backend == "local":
            full_path = self._full_path(path)
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)
            model.save(full_path)
        else:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".keras", delete=False) as tmp:
                tmp_path = tmp.name
            model.save(tmp_path)
            with open(tmp_path, "rb") as f:
                self.write_bytes(f.read(), path)
            Path(tmp_path).unlink()  # Clean up

    # ============================================================
    # File system operations
    # ============================================================
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        full_path = self._full_path(path)
        return self.fs.exists(full_path)

    def rm(self, path: str, recursive: bool = False) -> None:
        """Remove file or directory."""
        full_path = self._full_path(path)
        self.fs.rm(full_path, recursive=recursive)

    def ls(self, path: str = "") -> list[str]:
        """List files in directory."""
        full_path = self._full_path(path) if path else self.base_uri
        return self.fs.ls(full_path)

    def makedirs(self, path: str, exist_ok: bool = True) -> None:
        """Create directory (and parents)."""
        full_path = self._full_path(path)
        self.fs.makedirs(full_path, exist_ok=exist_ok)


def get_storage() -> StorageClient:
    """Get storage client instance."""
    return StorageClient()
