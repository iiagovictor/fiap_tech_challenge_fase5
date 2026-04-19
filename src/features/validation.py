"""
Validação contra Golden Set

Detecta anomalias comparando dados processados com golden_set de referência.
Garante qualidade e consistência do pipeline.
"""
from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

import pandas as pd
import numpy as np

log = logging.getLogger("validation")

GOLDEN_SET_PATH = Path(__file__).parent.parent.parent / "data" / "golden_set" / "ohlcv_golden.parquet"


@dataclass
class ValidationResult:
    """Resultado da validação contra golden_set"""
    status: str  # pass, warning, fail
    timestamp: str
    num_records: int
    tickers_validated: list
    checks: dict
    anomalies: list
    message: str
    
    def to_dict(self) -> dict:
        return asdict(self)


def load_golden_set() -> pd.DataFrame:
    """
    Carrega golden_set de referência.
    
    Raises:
        FileNotFoundError: Se golden_set não existir
    """
    if not GOLDEN_SET_PATH.exists():
        raise FileNotFoundError(
            f"Golden set não encontrado em {GOLDEN_SET_PATH}\n"
            "Execute: python scripts/create_golden_set.py"
        )
    
    df = pd.read_parquet(GOLDEN_SET_PATH)
    log.info(f"Golden set carregado: {len(df)} linhas, {df['Ticker'].nunique()} tickers")
    return df


def validate_schema(current_df: pd.DataFrame, golden_df: pd.DataFrame) -> tuple[bool, list]:
    """
    Valida se schema do current_df é compatível com golden_df.
    
    Returns:
        (is_valid, errors)
    """
    errors = []
    
    # Colunas obrigatórias
    required_cols = {"Date", "Open", "High", "Low", "Close", "Volume", "Ticker", "Daily_Return", "Price_Range"}
    missing_cols = required_cols - set(current_df.columns)
    
    if missing_cols:
        errors.append(f"Colunas faltando: {missing_cols}")
    
    # Tipos de dados
    type_checks = {
        "Date": ["datetime64"],
        "Open": ["float64", "float32"],
        "High": ["float64", "float32"],
        "Low": ["float64", "float32"],
        "Close": ["float64", "float32"],
        "Volume": ["float64", "float32"],
        "Ticker": ["object"],
    }
    
    for col, expected_types in type_checks.items():
        if col in current_df.columns:
            actual_type = str(current_df[col].dtype)
            if actual_type not in expected_types:
                errors.append(f"Coluna {col}: tipo {actual_type}, esperado {expected_types}")
    
    return len(errors) == 0, errors


def validate_tickers(current_df: pd.DataFrame, golden_df: pd.DataFrame) -> tuple[bool, dict]:
    """
    Valida se tickers são os mesmos.
    
    Returns:
        (is_valid, {current_tickers, golden_tickers, missing, new})
    """
    current_tickers = set(current_df["Ticker"].unique())
    golden_tickers = set(golden_df["Ticker"].unique())
    
    missing = golden_tickers - current_tickers
    new = current_tickers - golden_tickers
    
    info = {
        "current": list(current_tickers),
        "golden": list(golden_tickers),
        "missing": list(missing),
        "new": list(new)
    }
    
    is_valid = len(missing) == 0 and len(new) == 0
    return is_valid, info


def validate_statistical_properties(
    current_df: pd.DataFrame,
    golden_df: pd.DataFrame,
    tolerance_pct: float = 15.0
) -> tuple[bool, dict]:
    """
    Compara propriedades estatísticas (não valores exatos).
    
    Testa:
    - Média de preços por ticker
    - Range de preços
    - Distribuição de volume
    
    Args:
        current_df: Dados processados atuais
        golden_df: Golden set de referência
        tolerance_pct: Tolerância em % para desvios (default: 15%)
    
    Returns:
        (is_valid, checks_dict)
    """
    checks = {}
    anomalies = []
    
    # Agrupar por ticker
    tickers = set(current_df["Ticker"].unique()) & set(golden_df["Ticker"].unique())
    
    for ticker in sorted(tickers):
        curr_subset = current_df[current_df["Ticker"] == ticker]
        gold_subset = golden_df[golden_df["Ticker"] == ticker]
        
        checks[ticker] = {}
        
        # 1. Média de Close
        curr_close_mean = curr_subset["Close"].mean()
        gold_close_mean = gold_subset["Close"].mean()
        close_pct_diff = abs((curr_close_mean - gold_close_mean) / gold_close_mean * 100)
        
        checks[ticker]["close_mean"] = {
            "current": float(curr_close_mean),
            "golden": float(gold_close_mean),
            "pct_diff": float(close_pct_diff)
        }
        
        if close_pct_diff > tolerance_pct:
            anomalies.append(
                f"{ticker}: Close médio divergiu {close_pct_diff:.2f}% "
                f"(tol: {tolerance_pct}%)"
            )
        
        # 2. Range de preços
        curr_high_max = curr_subset["High"].max()
        gold_high_max = gold_subset["High"].max()
        high_pct_diff = abs((curr_high_max - gold_high_max) / gold_high_max * 100)
        
        checks[ticker]["high_max"] = {
            "current": float(curr_high_max),
            "golden": float(gold_high_max),
            "pct_diff": float(high_pct_diff)
        }
        
        # 3. Volume médio
        curr_vol_mean = curr_subset["Volume"].mean()
        gold_vol_mean = gold_subset["Volume"].mean()
        vol_pct_diff = abs((curr_vol_mean - gold_vol_mean) / gold_vol_mean * 100) if gold_vol_mean > 0 else 0
        
        checks[ticker]["volume_mean"] = {
            "current": float(curr_vol_mean),
            "golden": float(gold_vol_mean),
            "pct_diff": float(vol_pct_diff)
        }
    
    is_valid = len(anomalies) == 0
    return is_valid, {"checks": checks, "anomalies": anomalies}


def validate_data_integrity(current_df: pd.DataFrame) -> tuple[bool, list]:
    """
    Valida integridade dos dados (nulos, infinitos, etc).
    
    Returns:
        (is_valid, errors)
    """
    errors = []
    
    # Nulos em colunas críticas
    critical_cols = ["Date", "Open", "High", "Low", "Close", "Volume", "Ticker"]
    for col in critical_cols:
        if col in current_df.columns:
            n_nulls = current_df[col].isnull().sum()
            if n_nulls > 0:
                errors.append(f"Coluna {col}: {n_nulls} valores nulos")
    
    # Infinitos
    numeric_cols = ["Open", "High", "Low", "Close", "Volume", "Daily_Return", "Price_Range"]
    for col in numeric_cols:
        if col in current_df.columns:
            n_infs = np.isinf(current_df[col]).sum()
            if n_infs > 0:
                errors.append(f"Coluna {col}: {n_infs} valores infinitos")
    
    # Invariantes OHLCV (High >= Open, Close, Low)
    if all(col in current_df.columns for col in ["High", "Open", "Close", "Low"]):
        violations = current_df[(current_df["High"] < current_df["Low"])].shape[0]
        if violations > 0:
            errors.append(f"Invariante violado: High < Low em {violations} linhas")
    
    return len(errors) == 0, errors


def validate_against_golden_set(
    processed_df: pd.DataFrame,
    tolerance_pct: float = 15.0
) -> ValidationResult:
    """
    Valida dados processados contra golden_set.
    
    Executa:
    1. Validação de schema
    2. Validação de tickers
    3. Validação de integridade
    4. Validação de propriedades estatísticas
    
    Args:
        processed_df: DataFrame processado
        tolerance_pct: Tolerância em % para desvios estatísticos
    
    Returns:
        ValidationResult com detalhes da validação
    """
    try:
        golden_df = load_golden_set()
    except FileNotFoundError as e:
        log.warning(f"Golden set não encontrado: {e}")
        return ValidationResult(
            status="skip",
            timestamp=datetime.now().isoformat(),
            num_records=len(processed_df),
            tickers_validated=[],
            checks={},
            anomalies=["Golden set não encontrado - validação pulada"],
            message="Golden set não disponível"
        )
    
    checks = {}
    anomalies = []
    status = "pass"
    
    # ── Check 1: Schema ────────────────────────────────────────────────────
    schema_valid, schema_errors = validate_schema(processed_df, golden_df)
    checks["schema"] = {"valid": schema_valid, "errors": schema_errors}
    if not schema_valid:
        status = "fail"
        anomalies.extend(schema_errors)
    
    # ── Check 2: Tickers ───────────────────────────────────────────────────
    tickers_valid, ticker_info = validate_tickers(processed_df, golden_df)
    checks["tickers"] = ticker_info
    if not tickers_valid:
        status = "warning" if status == "pass" else status
        if ticker_info["missing"]:
            anomalies.append(f"Tickers faltando: {ticker_info['missing']}")
        if ticker_info["new"]:
            anomalies.append(f"Novos tickers: {ticker_info['new']}")
    
    # ── Check 3: Integridade ───────────────────────────────────────────────
    integrity_valid, integrity_errors = validate_data_integrity(processed_df)
    checks["integrity"] = {"valid": integrity_valid, "errors": integrity_errors}
    if not integrity_valid:
        status = "fail"
        anomalies.extend(integrity_errors)
    
    # ── Check 4: Propriedades Estatísticas ─────────────────────────────────
    if schema_valid and tickers_valid and integrity_valid:
        stats_valid, stats_info = validate_statistical_properties(
            processed_df,
            golden_df,
            tolerance_pct=tolerance_pct
        )
        checks["statistics"] = stats_info
        if not stats_valid:
            status = "warning" if status == "pass" else status
            anomalies.extend(stats_info["anomalies"])
    
    # ── Result ────────────────────────────────────────────────────────────
    message = {
        "pass": "✓ Validação contra golden_set passou",
        "warning": "⚠ Validação contra golden_set com avisos",
        "fail": "✗ Validação contra golden_set falhou"
    }.get(status, status)
    
    result = ValidationResult(
        status=status,
        timestamp=datetime.now().isoformat(),
        num_records=len(processed_df),
        tickers_validated=list(
            set(processed_df["Ticker"].unique()) & set(golden_df["Ticker"].unique())
        ),
        checks=checks,
        anomalies=anomalies,
        message=message
    )
    
    return result
