"""
Testes para validação contra Golden Set

Cobre:
- Criação do golden_set
- Validação de schema
- Validação de tickers
- Validação de propriedades estatísticas
- Detecção de anomalias
"""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.validation import (
    load_golden_set,
    validate_schema,
    validate_tickers,
    validate_data_integrity,
    validate_statistical_properties,
    validate_against_golden_set,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def golden_set_path():
    """Path do golden_set"""
    path = Path("data/golden_set/ohlcv_golden.parquet")
    return path


@pytest.fixture
def valid_processed_df() -> pd.DataFrame:
    """DataFrame processado válido"""
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=10),
            "Open": [100.0, 101.0, 102.0, 101.5, 103.0, 102.5, 104.0, 103.5, 105.0, 104.5],
            "High": [102.0, 103.0, 104.0, 103.5, 105.0, 104.5, 106.0, 105.5, 107.0, 106.5],
            "Low": [99.0, 100.0, 101.0, 100.5, 102.0, 101.5, 103.0, 102.5, 104.0, 103.5],
            "Close": [101.0, 102.0, 103.0, 102.5, 104.0, 103.5, 105.0, 104.5, 106.0, 105.5],
            "Volume": [1_000_000.0] * 10,
            "Ticker": ["AAPL"] * 10,
            "Daily_Return": [None] + [0.01] * 9,
            "Price_Range": [3.0] * 10,
        }
    )


@pytest.fixture
def golden_df(valid_processed_df) -> pd.DataFrame:
    """Golden set de referência"""
    return valid_processed_df.copy()


# ── Testes: Carregamento ──────────────────────────────────────────────────

class TestGoldenSetLoading:
    """Testes para carregamento do golden_set"""
    
    def test_golden_set_exists(self, golden_set_path):
        """Verifica se golden_set existe (skip se não existir)"""
        if not golden_set_path.exists():
            pytest.skip("Golden set não existe - crie com: python scripts/create_golden_set.py")
        assert golden_set_path.exists()
    
    def test_load_golden_set(self, golden_set_path):
        """Testa carregamento do golden_set"""
        if not golden_set_path.exists():
            pytest.skip("Golden set não existe")
        
        df = load_golden_set()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_golden_set_has_required_columns(self, golden_set_path):
        """Verifica se golden_set tem colunas obrigatórias"""
        if not golden_set_path.exists():
            pytest.skip("Golden set não existe")
        
        df = pd.read_parquet(golden_set_path)
        required_cols = {"Date", "Open", "High", "Low", "Close", "Volume", "Ticker", "Daily_Return", "Price_Range"}
        assert required_cols.issubset(df.columns), f"Colunas faltando: {required_cols - set(df.columns)}"


# ── Testes: Schema Validation ──────────────────────────────────────────────

class TestSchemaValidation:
    """Testes para validação de schema"""
    
    def test_valid_schema_passes(self, valid_processed_df, golden_df):
        """Schema válido deve passar"""
        is_valid, errors = validate_schema(valid_processed_df, golden_df)
        assert is_valid
        assert len(errors) == 0
    
    def test_missing_column_fails(self, valid_processed_df, golden_df):
        """Schema com coluna faltando deve falhar"""
        df = valid_processed_df.drop(columns=["Daily_Return"])
        is_valid, errors = validate_schema(df, golden_df)
        assert not is_valid
        assert len(errors) > 0
    
    def test_wrong_dtype_fails(self, valid_processed_df, golden_df):
        """Schema com tipo incorreto deve falhar"""
        df = valid_processed_df.copy()
        df["Close"] = df["Close"].astype(int)  # deve ser float
        is_valid, errors = validate_schema(df, golden_df)
        assert not is_valid
        assert len(errors) > 0


# ── Testes: Ticker Validation ──────────────────────────────────────────────

class TestTickerValidation:
    """Testes para validação de tickers"""
    
    def test_same_tickers_pass(self, valid_processed_df, golden_df):
        """Mesmo conjunto de tickers deve passar"""
        is_valid, info = validate_tickers(valid_processed_df, golden_df)
        assert is_valid
        assert len(info["missing"]) == 0
        assert len(info["new"]) == 0
    
    def test_missing_ticker_detected(self, valid_processed_df, golden_df):
        """Ticker faltando deve ser detectado"""
        df = valid_processed_df[valid_processed_df["Ticker"] != "AAPL"]
        is_valid, info = validate_tickers(df, golden_df)
        assert not is_valid
        assert "AAPL" in info["missing"]
    
    def test_new_ticker_detected(self, valid_processed_df, golden_df):
        """Novo ticker deve ser detectado"""
        df = pd.concat([
            valid_processed_df,
            valid_processed_df.assign(Ticker="MSFT")
        ])
        is_valid, info = validate_tickers(df, golden_df)
        assert not is_valid
        assert "MSFT" in info["new"]


# ── Testes: Data Integrity ────────────────────────────────────────────────

class TestDataIntegrity:
    """Testes para validação de integridade de dados"""
    
    def test_valid_data_passes(self, valid_processed_df):
        """Dados válidos devem passar"""
        is_valid, errors = validate_data_integrity(valid_processed_df)
        assert is_valid
        assert len(errors) == 0
    
    def test_nulls_detected(self, valid_processed_df):
        """Nulos devem ser detectados"""
        df = valid_processed_df.copy()
        df.loc[0, "Close"] = None
        is_valid, errors = validate_data_integrity(df)
        assert not is_valid
        assert len(errors) > 0
    
    def test_infinities_detected(self, valid_processed_df):
        """Infinitos devem ser detectados"""
        df = valid_processed_df.copy()
        df.loc[0, "Close"] = np.inf
        is_valid, errors = validate_data_integrity(df)
        assert not is_valid
        assert len(errors) > 0
    
    def test_ohlc_invariant_violation_detected(self, valid_processed_df):
        """Violação de invariante OHLCV deve ser detectada"""
        df = valid_processed_df.copy()
        df.loc[0, "High"] = 50.0  # Menor que Low (99.0)
        is_valid, errors = validate_data_integrity(df)
        assert not is_valid
        assert len(errors) > 0


# ── Testes: Statistical Properties ─────────────────────────────────────────

class TestStatisticalValidation:
    """Testes para validação de propriedades estatísticas"""
    
    def test_identical_data_passes(self, valid_processed_df, golden_df):
        """Dados idênticos devem passar"""
        is_valid, result = validate_statistical_properties(valid_processed_df, golden_df)
        assert is_valid
        assert len(result["anomalies"]) == 0
    
    def test_small_deviation_passes(self, valid_processed_df, golden_df):
        """Pequeno desvio deve passar"""
        df = valid_processed_df.copy()
        df["Close"] = df["Close"] * 1.05  # +5% de desvio
        
        is_valid, result = validate_statistical_properties(df, golden_df, tolerance_pct=10)
        assert is_valid
    
    def test_large_deviation_detected(self, valid_processed_df, golden_df):
        """Grande desvio deve ser detectado"""
        df = valid_processed_df.copy()
        df["Close"] = df["Close"] * 1.50  # +50% de desvio
        
        is_valid, result = validate_statistical_properties(df, golden_df, tolerance_pct=10)
        assert not is_valid
        assert len(result["anomalies"]) > 0


# ── Testes: Complete Validation ────────────────────────────────────────────

class TestCompleteValidation:
    """Testes para validação completa"""
    
    def test_valid_data_passes_complete_validation(self, valid_processed_df, golden_df, monkeypatch):
        """Dados válidos devem passar validação completa"""
        # Mock load_golden_set para retornar golden_df
        def mock_load():
            return golden_df
        
        monkeypatch.setattr("features.validation.load_golden_set", mock_load)
        
        result = validate_against_golden_set(valid_processed_df)
        assert result.status == "pass"
        assert result.num_records == len(valid_processed_df)
    
    def test_invalid_data_fails_validation(self, valid_processed_df, golden_df, monkeypatch):
        """Dados inválidos devem falhar"""
        def mock_load():
            return golden_df
        
        monkeypatch.setattr("features.validation.load_golden_set", mock_load)
        
        df = valid_processed_df.copy()
        df.loc[0, "Close"] = None  # Criar nulo
        
        result = validate_against_golden_set(df)
        assert result.status == "fail"
        assert len(result.anomalies) > 0
    
    def test_missing_ticker_warning(self, valid_processed_df, golden_df, monkeypatch):
        """Ticker faltando deve gerar warning"""
        def mock_load():
            return golden_df
        
        monkeypatch.setattr("features.validation.load_golden_set", mock_load)
        
        df = valid_processed_df[valid_processed_df["Ticker"] != "AAPL"]
        
        result = validate_against_golden_set(df)
        assert result.status == "warning"
        assert any("faltando" in a.lower() for a in result.anomalies)
    
    def test_result_serializable(self, valid_processed_df, golden_df, monkeypatch):
        """Resultado deve ser serializável para JSON"""
        def mock_load():
            return golden_df
        
        monkeypatch.setattr("features.validation.load_golden_set", mock_load)
        
        result = validate_against_golden_set(valid_processed_df)
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert "status" in result_dict
        assert "timestamp" in result_dict


# ── Integration Tests ──────────────────────────────────────────────────────

class TestGoldenSetIntegration:
    """Testes de integração com golden_set real (se existir)"""
    
    def test_with_real_golden_set(self, golden_set_path):
        """Testa com golden_set real se existir"""
        if not golden_set_path.exists():
            pytest.skip("Golden set real não existe")
        
        golden_df = pd.read_parquet(golden_set_path)
        
        # Validar golden_set contra si mesmo (deve passar)
        result = validate_against_golden_set(golden_df)
        
        # Pode ser pass ou warning (não deve ser fail)
        assert result.status in ["pass", "warning"]
        assert len(result.tickers_validated) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
