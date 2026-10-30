# Engine contract: fraud scoring

## Latency
End-to-end decision under 300 ms at p95. Current p95: 180 ms on the GPU pool.

## Interfaces
Scoring service accepts a transaction JSON and returns {score, flag, reasons[3]}. The analyst dashboard reads reasons[] directly, so the reasons format must not change without a dashboard update.

## Approved libraries
Python 3.11, xgboost 2.x, scikit-learn 1.5+, shap 0.45+, pandas 2.x. Deep learning frameworks (PyTorch) are not approved for the scoring service yet.

## Hardware
Serving runs on a small GPU pool. A CPU-only move is possible for tree models; XGBoost on CPU adds about 60 ms at p95.
