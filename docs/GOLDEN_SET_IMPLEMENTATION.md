# Golden Set Implementation Guide

## 📌 O que é Golden Set?

O **golden_set** (conjunto de ouro) é um conjunto de dados de **referência validados manualmente** que serve para:

1. **Testes de Regressão**: Garantir que mudanças no código não degradem a qualidade
2. **Validação de Qualidade**: Comparar dados processados com referência conhecida
3. **Benchmarking**: Medir performance do pipeline
4. **Testes Automatizados**: Suite de testes com dados conhecidos
5. **Documentação**: Exemplificar o comportamento esperado

## 🎯 Etapas Recomendadas para Implementação

### Etapa 1: **Criar Golden Set após Processamento** ✅ (RECOMENDADO)
**Localização**: `data/golden_set/`

**Por que aqui?**
- ✅ Dados já estão validados (schema Pandera)
- ✅ Limpeza e enriquecimento já aplicados
- ✅ Formato final (Parquet) estável
- ✅ Referência de qualidade mais alta

**O que incluir**:
```
data/golden_set/
├── ohlcv_golden.parquet        # Dados validados de referência
├── schema.yaml                  # Metadados do golden_set
└── README.md                    # Documentação
```

### Etapa 2: **Adicionar Validação contra Golden Set**
**Localização**: `src/features/validation.py` (novo arquivo)

**Função**: Comparar dados processados com golden_set
```python
def validate_against_golden_set(processed_df, golden_df):
    """
    Valida dados processados contra golden_set.
    Não testa valores exatos, mas:
    - Range de valores
    - Distribuição estatística
    - Correlações entre colunas
    - Anomalias incomuns
    """
```

### Etapa 3: **Integrar Golden Set nos Testes**
**Localização**: `tests/test_golden_set.py` (novo arquivo)

**Testes**:
- Validação de schema do golden_set
- Comparação de estatísticas
- Testes de regressão

### Etapa 4: **Criar Pipeline de Certificação**
**Localização**: Script de atualização do golden_set

**Quando atualizar**:
- Após mudanças significativas no pipeline
- Com análise manual de qualidade
- Versionado (ex: golden_v1, golden_v2)

---

## 🏗️ Arquitetura Proposta

```
PRODUÇÃO
├── Dados Raw (yfinance)
│   └── data/raw/ohlcv_raw.csv
│       ↓
├── Processamento
│   └── src/features/process.py
│       ↓
├── Dados Processados (Parquet)
│   └── data/processed/ohlcv_processed.parquet
│       ↓
├── [NOVO] Validação contra Golden Set
│   └── src/features/validation.py
│       └── Comparação com data/golden_set/ohlcv_golden.parquet
│           ↓
├── Alertas (se falhar validação)
│   └── Logs, CloudWatch, etc.
│       ↓
└── Consumidores (ML, Dashboards, APIs)
```

---

## 💻 Implementação Prática

### Step 1: Criar Golden Set

```bash
# 1. Rodar pipeline normal
make pipeline

# 2. Validar manualmente os dados
# - Verificar valores outliers
# - Confirmar que tickers estão corretos
# - Validar período de tempo

# 3. Exportar como golden_set
python -c "
import pandas as pd
df = pd.read_parquet('data/processed/ohlcv_processed.parquet')
df.to_parquet('data/golden_set/ohlcv_golden.parquet', index=False)
print(f'✓ Golden set criado: {len(df)} linhas')
"
```

### Step 2: Adicionar Validação

Criar `src/features/validation.py`:

```python
"""
Validação contra Golden Set

Detecta anomalias comparando dados processados com golden_set.
"""
import pandas as pd
import numpy as np
from pathlib import Path

GOLDEN_SET_PATH = Path(__file__).parent.parent.parent / "data" / "golden_set" / "ohlcv_golden.parquet"


def load_golden_set() -> pd.DataFrame:
    """Carrega golden_set de referência."""
    if not GOLDEN_SET_PATH.exists():
        raise FileNotFoundError(f"Golden set não encontrado: {GOLDEN_SET_PATH}")
    return pd.read_parquet(GOLDEN_SET_PATH)


def validate_statistical_properties(current_df: pd.DataFrame, golden_df: pd.DataFrame) -> dict:
    """
    Compara propriedades estatísticas.
    Não testa valores exatos, mas padrões.
    """
    results = {
        "status": "pass",
        "checks": {},
        "anomalies": []
    }
    
    # Comparar médias de preços
    for ticker in current_df["Ticker"].unique():
        curr_subset = current_df[current_df["Ticker"] == ticker]
        gold_subset = golden_df[golden_df["Ticker"] == ticker]
        
        if len(gold_subset) == 0:
            results["anomalies"].append(f"Ticker {ticker} não existe em golden_set")
            continue
        
        # Estatísticas
        curr_mean_close = curr_subset["Close"].mean()
        gold_mean_close = gold_subset["Close"].mean()
        
        # Calcular desvio em %
        pct_diff = abs((curr_mean_close - gold_mean_close) / gold_mean_close * 100)
        
        # Flag se desvio > 10%
        if pct_diff > 10:
            results["status"] = "warning"
            results["anomalies"].append(
                f"{ticker}: Close médio divergiu {pct_diff:.2f}% "
                f"(golden: {gold_mean_close:.2f}, current: {curr_mean_close:.2f})"
            )
        
        results["checks"][ticker] = {
            "pct_diff": pct_diff,
            "golden_mean": gold_mean_close,
            "current_mean": curr_mean_close
        }
    
    return results


def validate_against_golden_set(processed_df: pd.DataFrame) -> dict:
    """
    Valida dados processados contra golden_set.
    
    Returns:
        Dict com status, checks realizados e anomalias detectadas
    """
    golden_df = load_golden_set()
    
    # Executar validações
    stats_result = validate_statistical_properties(processed_df, golden_df)
    
    return {
        "status": stats_result["status"],
        "statistics": stats_result,
        "timestamp": pd.Timestamp.now().isoformat()
    }
```

### Step 3: Integrar no Pipeline

Modificar `src/features/process.py`:

```python
from validation import validate_against_golden_set

def main() -> None:
    # ... código existente ...
    
    # Persistência
    PROCESSED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_OUTPUT, index=False)
    log.info("Processed data saved → %s (%d rows)", PROCESSED_OUTPUT, len(df))
    
    # [NOVO] Validação contra Golden Set
    try:
        log.info("Validating against golden_set...")
        validation_result = validate_against_golden_set(df)
        
        if validation_result["status"] == "warning":
            log.warning("Golden set validation warnings detected")
            for anomaly in validation_result["statistics"]["anomalies"]:
                log.warning(f"  - {anomaly}")
        else:
            log.info("✓ Golden set validation passed")
            
    except FileNotFoundError:
        log.info("Golden set not found - skipping validation (first run?)")
```

### Step 4: Testes

Criar `tests/test_golden_set.py`:

```python
"""
Testes para validação contra golden_set
"""
import pytest
import pandas as pd
from pathlib import Path

from src.features.validation import validate_against_golden_set


class TestGoldenSetValidation:
    """Testes de validação contra golden_set"""
    
    @pytest.fixture
    def golden_set_path(self):
        path = Path("data/golden_set/ohlcv_golden.parquet")
        if not path.exists():
            pytest.skip("Golden set não encontrado")
        return path
    
    def test_golden_set_exists(self, golden_set_path):
        """Verifica se golden_set existe"""
        assert golden_set_path.exists(), "Golden set deve existir"
    
    def test_golden_set_has_data(self, golden_set_path):
        """Verifica se golden_set tem dados"""
        df = pd.read_parquet(golden_set_path)
        assert len(df) > 0, "Golden set deve ter dados"
    
    def test_golden_set_schema(self, golden_set_path):
        """Valida schema do golden_set"""
        df = pd.read_parquet(golden_set_path)
        required_cols = {"Date", "Open", "High", "Low", "Close", "Volume", "Ticker", "Daily_Return", "Price_Range"}
        assert required_cols.issubset(df.columns), f"Golden set deve ter colunas: {required_cols}"
    
    def test_validate_against_golden_set(self, golden_set_path):
        """Testa validação contra golden_set"""
        golden_df = pd.read_parquet(golden_set_path)
        
        # Usar golden_set como dados processados (deve passar)
        result = validate_against_golden_set(golden_df)
        
        assert result["status"] in ["pass", "warning"]
        assert "statistics" in result
```

---

## 📊 Quando Atualizar Golden Set

### ✅ Situações para Atualizar

1. **Mudança de Fonte de Dados**
   - Novo provedor de dados (yfinance → outro)
   - Período histórico expandido

2. **Melhora Deliberada de Qualidade**
   - Novo schema Pandera
   - Melhor limpeza de dados
   - Novo enriquecimento (features)

3. **Versionamento**
   ```
   data/golden_set/
   ├── ohlcv_golden_v1.parquet  # Versão 1 (baseline)
   ├── ohlcv_golden_v2.parquet  # Versão 2 (após melhoria X)
   └── VERSIONS.md              # Changelog
   ```

### ❌ Situações para NÃO Atualizar

- Variações naturais de dados (preços flutuam)
- Falha de pipeline (problema de ingestão)
- Dados corrompidos

---

## 🔍 Exemplo de Workflow

```bash
# 1. Desenvolvimento: Executar pipeline
make pipeline

# 2. Validação Manual
# - Abrir data/processed/ohlcv_processed.parquet
# - Verificar estatísticas
# - Confirmar qualidade

# 3. Atualizar Golden Set (após validação)
python scripts/create_golden_set.py

# 4. Commit
git add data/golden_set/
git commit -m "Update golden_set v2 after schema improvements"

# 5. Deploy
# - Tests rodão com golden_set
# - Produção usa validação contra golden_set
```

---

## 📈 Métricas a Rastrear

Adicionar logging para rastrear divergências:

```python
@dataclass
class GoldenSetMetrics:
    timestamp: str
    num_records: int
    tickers: list
    price_divergence: dict      # % para cada ticker
    volume_divergence: dict
    missing_tickers: list
    new_tickers: list
    status: str                 # pass, warning, fail
```

---

## 🎯 Resumo: Etapas na Ordem Correta

| Ordem | Etapa | Arquivo | Prioridade |
|-------|-------|---------|-----------|
| 1 | Criar Golden Set (Parquet) | `data/golden_set/ohlcv_golden.parquet` | 🔴 ALTA |
| 2 | Implementar Validação | `src/features/validation.py` | 🟡 MÉDIA |
| 3 | Integrar no Pipeline | `src/features/process.py` | 🟡 MÉDIA |
| 4 | Adicionar Testes | `tests/test_golden_set.py` | 🟢 BAIXA |
| 5 | Versionamento | `data/golden_set/VERSIONS.md` | 🟢 BAIXA |

---

## 📚 Referências

- [Data Quality Testing](https://www.databricks.com/blog/2022/06/23/schema-and-data-quality-checks.html)
- [Golden Dataset Pattern](https://towardsdatascience.com/data-quality-testing-in-data-pipelines-3d2f6e6a0e7d)
- [Feature Store Golden Sets](https://tecton.ai/blog/feature-store-best-practices/)
