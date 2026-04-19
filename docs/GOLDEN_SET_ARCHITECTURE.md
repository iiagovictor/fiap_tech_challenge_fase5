# Golden Set - Diagram and Architecture

## 📊 Pipeline Completo com Golden Set

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PRODUÇÃO - DATA PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────┘

ETAPA 1: INGESTÃO
├─ Fonte: yfinance
├─ Output: data/raw/ohlcv_raw.csv
└─ Validação: Tipo e formato

    ↓

ETAPA 2: PROCESSAMENTO
├─ Input: data/raw/ohlcv_raw.csv
├─ Limpeza: Duplicatas, nulos, tipos
├─ Enriquecimento: Daily_Return, Price_Range
├─ Validação Schema: Pandera (validação rigorosa)
└─ Output: data/processed/ohlcv_processed.parquet

    ↓

ETAPA 3: VALIDAÇÃO CONTRA GOLDEN SET ⭐ (NOVO)
├─ Carrega: data/golden_set/ohlcv_golden.parquet
├─ Compara:
│  ├─ Schema (tipos, colunas)
│  ├─ Tickers (presentes, novos, faltando)
│  ├─ Integridade (nulos, infinitos, invariantes)
│  └─ Estatísticas (média, range, volume)
├─ Reporta: Anomalias detectadas
└─ Ação: Log (não interrompe pipeline)

    ↓

ETAPA 4: CONSUMO
├─ ML Models
├─ Dashboards
├─ APIs
└─ Análises
```

## 🔄 Fluxo de Criação do Golden Set

```
PRIMEIRA VEZ: Setup do Golden Set

1. Executar pipeline completo
   $ make pipeline
   
2. Validar dados manualmente
   - Abrir processed/ohlcv_processed.parquet
   - Verificar outliers, gaps, valores extremos
   - Confirmar tickers, períodos, volumes
   
3. Criar golden_set
   $ make golden-create
   ✓ Golden set criado em: data/golden_set/ohlcv_golden.parquet
   
4. Commit para versionamento
   $ git add data/golden_set/
   $ git commit -m "Add golden_set v1"

PRÓXIMAS EXECUÇÕES:

1. Pipeline normal
   $ make pipeline
   
2. Validação automática contra golden_set
   [INFO] Validating against golden_set...
   [INFO] ✓ Golden set validation PASSED
   
3. Dados prontos para consumo ✓
```

## 📈 Estrutura de Dados

```
data/
├── raw/
│   └── ohlcv_raw.csv                    # 1M+ linhas
│       ├─ Columns: Date, Open, High, Low, Close, Volume, Ticker
│       └─ Source: yfinance
│
├── processed/
│   └── ohlcv_processed.parquet          # 1M+ linhas
│       ├─ Columns: ^^ + Daily_Return, Price_Range
│       ├─ Schema: Pandera validado ✓
│       └─ Format: Parquet (otimizado)
│
└── golden_set/                          # ⭐ NOVO
    ├── ohlcv_golden.parquet            # ~10k-100k linhas
    ├── ohlcv_golden_v1.parquet         # Versão 1 (opcional)
    ├── ohlcv_golden_v2.parquet         # Versão 2 (opcional)
    ├── VERSIONS.md                      # Changelog
    └── README.md                        # Documentação
```

## 🎯 Uso dos Dados

```
Golden Set é DIFERENTE de Processed:

┌─────────────────────────────────────────┐
│       DADOS PROCESSADOS (Produção)     │
├─────────────────────────────────────────┤
│ ✓ Dados reais, atuais                   │
│ ✓ Usado para ML, dashboards, APIs       │
│ ✗ Pode ter anomalias eventuais          │
│ ✗ Muda constantemente (novos dados)     │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│        GOLDEN SET (Referência)          │
├─────────────────────────────────────────┤
│ ✓ Dados validados manualmente           │
│ ✓ Usado para testes e validação         │
│ ✓ Estável (não muda)                    │
│ ✓ Benchmark de qualidade                │
│ ✗ Histórico (passado)                   │
│ ✗ Amostra (não todos os dados)          │
└─────────────────────────────────────────┘
```

## 🔍 Validações Executadas

```
┌─ SCHEMA VALIDATION
│  ├─ Colunas obrigatórias presentes?
│  ├─ Tipos de dados corretos?
│  └─ Formato correto?
│
├─ TICKER VALIDATION
│  ├─ Mesmo conjunto de tickers?
│  ├─ Tickers faltando?
│  └─ Novos tickers adicionados?
│
├─ DATA INTEGRITY
│  ├─ Valores nulos?
│  ├─ Infinitos?
│  ├─ Invariantes OHLCV (High >= Low)?
│  └─ Dados corrompidos?
│
└─ STATISTICAL PROPERTIES
   ├─ Média de preços (~15% tolerância)
   ├─ Range de preços
   ├─ Volume médio
   └─ Distribuição de retornos
```

## 📊 Resultados Esperados

```
SCENARIO 1: Dados Normais ✓
┌────────────────────────────────────────┐
│ [INFO] Validating against golden_set...│
│ [INFO] ✓ Golden set validation PASSED  │
│ Status: pass                            │
│ Anomalies: []                           │
└────────────────────────────────────────┘

SCENARIO 2: Pequena Anomalia ⚠️
┌────────────────────────────────────────┐
│ [WARNING] Golden set validation...     │
│ [WARNING] AAPL: Close divergiu 12% ... │
│ Status: warning                         │
│ Anomalies: [1 item]                    │
│ Action: LOG ONLY (não interrompe)      │
└────────────────────────────────────────┘

SCENARIO 3: Erro Grave ❌
┌────────────────────────────────────────┐
│ [ERROR] Golden set validation FAILED   │
│ [ERROR] Coluna Daily_Return: 100 nulos │
│ Status: fail                            │
│ Anomalies: [1 item]                    │
│ Action: LOG ONLY (não interrompe)      │
└────────────────────────────────────────┘

SCENARIO 4: Golden Set Não Existe ⊘
┌────────────────────────────────────────┐
│ [INFO] Golden set validation SKIPPED   │
│ Reason: Golden set not found           │
│ Action: Pipeline continua normalmente  │
│         (use: make golden-create)      │
└────────────────────────────────────────┘
```

## 🔄 Ciclo de Vida

```
1. BASELINE CREATION (Primeira Vez)
   - Executar pipeline: make pipeline
   - Validar manualmente os dados
   - Criar golden_set: make golden-create
   - Commit: git add data/golden_set/

2. CONTINUOUS VALIDATION (Diariamente)
   - EventBridge dispara pipeline
   - Dados processados
   - Validação contra golden_set automática
   - Alertas se anomalias detectadas

3. MAINTENANCE (Quando Necessário)
   - Se mudanças no schema: atualizar golden_set
   - Se melhoria de qualidade: nova versão (v2, v3)
   - Se bug encontrado: corrigir e re-validar

4. VERSIONING (Opcional)
   - Manter histórico: ohlcv_golden_v1.parquet
   - Rastrear mudanças: VERSIONS.md
   - Comparar versões para detectar regressões
```

## 💡 Melhores Práticas

```
✅ DO:
- Criar golden_set com dados que você validou manualmente
- Versionar quando fizer mudanças significativas
- Revisar anomalias detectadas regularmente
- Manter golden_set sincronizado com schema processado
- Documentar quando e por que atualizou

❌ DON'T:
- Não atualizar golden_set com dados sem validação
- Não ignorar avisos da validação
- Não deixar golden_set desatualizado
- Não usar como dataset de treinamento (data leakage!)
- Não acreditar cegamente (validar depois)
```

## 🚀 Próximas Etapas

1. ✅ Criar golden_set inicial: `make golden-create`
2. ✅ Executar testes: `make test`
3. ✅ Revisar logs de validação
4. ✅ Configurar alertas (CloudWatch)
5. ✅ Integrar com CI/CD (GitHub Actions)
