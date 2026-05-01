# Model Card: LSTM Stock Price Direction Predictor

## Model Details

**Model Name:** LSTM Stock Price Direction Predictor  
**Version:** 1.0.0  
**Date:** January 2025  
**Model Type:** Long Short-Term Memory (LSTM) Neural Network  
**Framework:** TensorFlow/Keras 2.x  
**License:** Proprietary (FIAP Tech Challenge Fase 5)

### Model Description

This model predicts the direction of stock price movement (up or down) over a 5-day horizon using historical price data and technical indicators from the Brazilian stock market (B3).

**Architecture:**
- Input: Sequences of 60 days with 24 features (OHLCV + technical indicators)
- LSTM Layer 1: 50 units with dropout (0.2)
- LSTM Layer 2: 25 units with dropout (0.2)
- Dense Layer: 32 units with ReLU activation and dropout (0.2)
- Output Layer: 1 unit with sigmoid activation (binary classification)

**Training Details:**
- Optimizer: Adam (learning rate: 0.001)
- Loss Function: Binary cross-entropy
- Batch Size: 32
- Epochs: Up to 50 (with early stopping, patience=10)
- Training Data: Brazilian stocks (ITUB4, PETR4, VALE3, BBDC4, BBAS3, ^BVSP)
- Date Range: 2020-01-01 to present

## Intended Use

### Primary Use Cases
- Short-term (5-day) stock price direction prediction
- Technical analysis support for Brazilian stocks
- Educational and research purposes

### Out-of-Scope Use Cases
- **NOT for automated trading without human oversight**
- **NOT for real-time high-frequency trading**
- **NOT for financial advice**
- **NOT for stocks outside the Brazilian market**

### Users
- Data scientists and ML engineers
- Financial analysts (as decision support tool)
- Researchers studying market prediction

## Factors

### Relevant Factors
- **Market**: Brazilian stock market (B3)
- **Sectors**: Banking (ITUB4, BBDC4, BBAS3), Energy (PETR4), Mining (VALE3)
- **Time Period**: Training data from 2020 onwards
- **Technical Indicators**: RSI, MACD, SMAs, EMAs, Bollinger Bands, ATR, OBV

### Evaluation Factors
- Market volatility
- Trading volume
- Economic events (interest rates, GDP, inflation)
- Sector-specific news

## Metrics

### Performance Metrics

**Test Set Performance (Latest):**
- Accuracy: ~0.55-0.60
- Precision: ~0.52-0.58
- Recall: ~0.50-0.60
- F1 Score: ~0.51-0.59
- ROC-AUC: ~0.50-0.55

**Baseline Comparisons:**
- Logistic Regression: ROC-AUC ~0.46
- Random Forest: ROC-AUC ~0.48
- **LSTM shows improvement over baselines**

### Decision Thresholds
- Default: 0.5 (balanced precision/recall)
- Conservative: 0.6 (higher precision, fewer false positives)
- Aggressive: 0.4 (higher recall, catch more opportunities)

### Performance Variation
- **Banking stocks**: Slightly better performance (more predictable)
- **Commodity stocks**: Higher variance (external factors)
- **High volatility periods**: Degraded accuracy
- **Low volume days**: Less reliable predictions

## Training Data

### Data Sources
- **Primary**: Yahoo Finance API (yfinance)
- **Tickers**: ITUB4.SA, PETR4.SA, VALE3.SA, BBDC4.SA, BBAS3.SA, ^BVSP
- **Date Range**: 2020-01-01 to present
- **Frequency**: Daily OHLCV data

### Data Preprocessing
1. Download historical data (yfinance)
2. Calculate 24 technical indicators:
   - Simple Moving Averages (5, 10, 20, 50 days)
   - Exponential Moving Averages (12, 26 days)
   - RSI (14 days)
   - MACD (12, 26, 9)
   - Bollinger Bands (20 days, 2 std)
   - ATR (14 days)
   - OBV, Volume MA (20 days)
   - Price changes (1-day, 5-day)
3. Create target: 1 if price increases after 5 days, 0 otherwise
4. Generate sequences (60-day windows)
5. Standardize features (StandardScaler)

### Data Splits
- Training: 60%
- Validation: 20%
- Test: 20%
- **Stratified by target class**

### Data Limitations
- **Survivorship bias**: Only includes currently active tickers
- **Limited history**: Only 2020 onwards (excludes pre-COVID patterns)
- **Missing external factors**: Economic indicators, news sentiment not included
- **Market hours only**: No after-hours trading data

## Evaluation Data

Same source and preprocessing as training data, but held-out temporal split to prevent data leakage.

## Ethical Considerations

### Risks
1. **Financial Loss**: Incorrect predictions can lead to monetary losses
2. **Over-reliance**: Users may trust model blindly without due diligence
3. **Market Manipulation**: Adversarial actors could exploit known patterns
4. **Bias**: Model trained on recent data may not generalize to new market regimes

### Mitigations
1. **Disclaimer**: Clear communication that this is NOT financial advice
2. **Human-in-the-loop**: Predictions should support, not replace, human judgment
3. **Monitoring**: Continuous drift detection and retraining
4. **Guardrails**: Input validation and output confidence thresholds
5. **Transparency**: Model card and documentation provided

### Fairness
- No demographic data used (focus on technical analysis)
- Equal treatment across all tickers
- No exclusion based on market cap or sector

## Caveats and Recommendations

### Known Limitations
1. **Market efficiency**: Stock prices already reflect available information
2. **Non-stationarity**: Financial markets change over time (concept drift)
3. **Black swan events**: Model cannot predict unprecedented events
4. **Correlation ≠ Causation**: Technical patterns may be spurious

### Recommendations
1. **Use as decision support**, not automated trading
2. **Combine with fundamental analysis**
3. **Set stop-loss limits** to manage risk
4. **Retrain regularly** (monthly recommended)
5. **Monitor drift metrics** (alerts at score > 0.15)
6. **Backtest before deployment** in new market conditions

### Update Schedule
- **Retraining**: Monthly (or when drift score > 0.15)
- **Model evaluation**: Weekly performance review
- **Feature engineering**: Quarterly review of indicators

## Contact

**Model Owner:** FIAP Tech Challenge Team  
**Date Created:** January 2025  
**Last Updated:** January 2025  
**Version:** 1.0.0

For questions or issues, contact the MLOps team via the project repository.

---

**Disclaimer:** This model is for educational and research purposes only. It does not constitute financial advice. Always conduct your own research and consult with licensed financial advisors before making investment decisions.
