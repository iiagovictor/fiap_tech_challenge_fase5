## 📊 Feature Store

Este projeto implementa um **Feature Store offline** com o objetivo de centralizar, padronizar e disponibilizar as variáveis (features) utilizadas pelo modelo de previsão de ações.

---

## 📁 Estrutura

```
data/
 └── feature_store/
      └── stock_features.parquet

src/
 └── feature_store/
      ├── build_stock_features.py
      ├── offline_store.py
      └── online_store.py
```

---

## 🧠 O que o Feature Store faz

O Feature Store é responsável por:

* Coletar dados históricos de ações (via Yahoo Finance)
* Gerar features a partir desses dados
* Armazenar essas features em formato `.parquet`
* Disponibilizar essas features para o modelo de machine learning

---

## ⚙️ Features geradas

Atualmente, o pipeline gera as seguintes features para cada ticker:

* `close` → preço de fechamento
* `return_1d` → retorno diário
* `return_7d` → retorno semanal
* `ma_7` → média móvel de 7 dias
* `ma_21` → média móvel de 21 dias
* `volatility_7` → volatilidade (desvio padrão dos retornos)

Essas features são armazenadas no arquivo:

```
data/feature_store/stock_features.parquet
```

---

## 🔄 Como gerar o Feature Store

Execute o script:

```bash
python src/feature_store/build_stock_features.py
```

Isso irá:

1. Buscar dados históricos das ações
2. Criar as features
3. Salvar tudo no arquivo `.parquet`

---

## 📥 Como consumir as features

### 🔹 Offline Store

Responsável por leitura do dataset completo:

```python
from src.feature_store.offline_store import buscar_features_ticker

df = buscar_features_ticker("ITUB4.SA")
```

---

### 🔹 Online Store

Responsável por fornecer dados prontos para o modelo:

```python
from src.feature_store.online_store import buscar_features_para_predicao

prices = buscar_features_para_predicao("ITUB4.SA", tamanho_janela=60)
```

---

## 🤖 Integração com o modelo

Antes, o modelo buscava os dados diretamente do Yahoo Finance:

```python
stock = yf.Ticker(ticker)
hist = stock.history(period="6mo")
prices = hist["Close"].tolist()
```

Agora, o modelo passa a consumir os dados do Feature Store:

```python
from src.feature_store.online_store import buscar_features_para_predicao

prices = buscar_features_para_predicao(
    ticker=ticker,
    tamanho_janela=60
)
```

---

## 📌 Benefícios dessa abordagem

* 🔁 Reprodutibilidade (dados versionados)
* ⚡ Performance (evita chamadas externas em tempo de execução)
* 🧩 Modularização (separação entre dados e modelo)
* 📈 Escalabilidade (facilidade para adicionar novas features)

---

## 🚀 Próximos passos

* Versionar o Feature Store com DVC
* Registrar experimentos no MLflow
* Evoluir o modelo para utilizar múltiplas features (multivariado)
* Implementar um Feature Store online (cache ou banco de baixa latência)
