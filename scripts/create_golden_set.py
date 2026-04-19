"""
Script para criar ou atualizar o Golden Set

O golden_set é um conjunto de dados de referência que serve para:
- Validação de regressão
- Testes automatizados
- Benchmarking

Uso:
    python scripts/create_golden_set.py               # Criar do processed atual
    python scripts/create_golden_set.py --version 2   # Versionar como v2
    python scripts/create_golden_set.py --validate     # Validar antes de criar
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("create_golden_set")

PROCESSED_DATA = PROJECT_ROOT / "data" / "processed" / "ohlcv_processed.parquet"
GOLDEN_SET_DIR = PROJECT_ROOT / "data" / "golden_set"
GOLDEN_SET_FILE = GOLDEN_SET_DIR / "ohlcv_golden.parquet"
GOLDEN_SET_VERSIONS = GOLDEN_SET_DIR / "VERSIONS.md"


def validate_data(df: pd.DataFrame) -> bool:
    """
    Valida dados antes de usar como golden_set.
    
    Returns:
        True se válido, False caso contrário
    """
    log.info("Validando dados...")
    
    # Verificar colunas obrigatórias
    required_cols = {"Date", "Open", "High", "Low", "Close", "Volume", "Ticker", "Daily_Return", "Price_Range"}
    missing = required_cols - set(df.columns)
    
    if missing:
        log.error(f"Colunas faltando: {missing}")
        return False
    
    # Verificar valores nulos
    nulls = df[required_cols].isnull().sum()
    if nulls.sum() > 0:
        log.error(f"Valores nulos encontrados:\n{nulls}")
        return False
    
    # Verificar invariantes OHLCV
    invalid_ohlcv = df[df["High"] < df["Low"]]
    if len(invalid_ohlcv) > 0:
        log.error(f"Invariantes OHLCV violados em {len(invalid_ohlcv)} linhas (High < Low)")
        return False
    
    # Estatísticas
    log.info(f"✓ Dados válidos: {len(df)} linhas, {df['Ticker'].nunique()} tickers")
    log.info(f"  - Período: {df['Date'].min()} a {df['Date'].max()}")
    log.info(f"  - Tickers: {sorted(df['Ticker'].unique())}")
    log.info(f"  - Price range: {df['Close'].min():.2f} - {df['Close'].max():.2f}")
    
    return True


def create_golden_set(version: str | None = None, validate: bool = True) -> Path:
    """
    Cria ou atualiza o golden_set.
    
    Args:
        version: Versão (ex: "v1", "v2"). Se None, sobrescreve o atual.
        validate: Se True, valida dados antes de criar.
    
    Returns:
        Caminho do arquivo criado
    """
    # Verificar se dados processados existem
    if not PROCESSED_DATA.exists():
        log.error(f"Dados processados não encontrados: {PROCESSED_DATA}")
        log.error("Execute: make pipeline")
        return None
    
    # Carregar dados processados
    log.info(f"Carregando dados processados: {PROCESSED_DATA}")
    df = pd.read_parquet(PROCESSED_DATA)
    
    # Validar se solicitado
    if validate and not validate_data(df):
        log.error("Validação falhou - golden_set não foi criado")
        return None
    
    # Criar diretório
    GOLDEN_SET_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determinar arquivo de destino
    if version:
        output_file = GOLDEN_SET_DIR / f"ohlcv_golden_{version}.parquet"
    else:
        output_file = GOLDEN_SET_FILE
    
    # Salvar
    log.info(f"Salvando golden_set: {output_file}")
    df.to_parquet(output_file, index=False)
    log.info(f"✓ Golden_set criado: {output_file}")
    
    # Atualizar VERSIONS.md
    update_versions_file(version or "default")
    
    return output_file


def update_versions_file(version: str) -> None:
    """Atualiza histórico de versões do golden_set."""
    
    entry = f"- **{version}**: {datetime.now().isoformat()} ({PROCESSED_DATA.stat().st_mtime})\n"
    
    if GOLDEN_SET_VERSIONS.exists():
        content = GOLDEN_SET_VERSIONS.read_text()
    else:
        content = "# Golden Set Versions\n\n"
    
    # Adicionar novo entry se não existir
    if version not in content:
        content = content.rstrip() + "\n" + entry
        GOLDEN_SET_VERSIONS.write_text(content)
        log.info(f"✓ Versão registrada em {GOLDEN_SET_VERSIONS}")


def list_golden_sets() -> None:
    """Lista golden_sets disponíveis."""
    if not GOLDEN_SET_DIR.exists():
        log.info("Nenhum golden_set encontrado")
        return
    
    files = list(GOLDEN_SET_DIR.glob("ohlcv_golden*.parquet"))
    if not files:
        log.info("Nenhum golden_set encontrado")
        return
    
    log.info("Golden sets disponíveis:")
    for f in sorted(files):
        df = pd.read_parquet(f)
        size_mb = f.stat().st_size / (1024 * 1024)
        log.info(f"  - {f.name}: {len(df)} linhas, {df['Ticker'].nunique()} tickers ({size_mb:.2f}MB)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Criar ou atualizar Golden Set para validação de qualidade"
    )
    parser.add_argument(
        "--version",
        type=str,
        help="Versão do golden_set (ex: v1, v2). Se omitido, sobrescreve o atual.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Validar dados antes de criar (default: True)",
    )
    parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Pular validação",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar golden_sets disponíveis",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_golden_sets()
        return 0
    
    result = create_golden_set(version=args.version, validate=args.validate)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
