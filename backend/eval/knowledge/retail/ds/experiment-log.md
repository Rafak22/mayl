# Experiment log (forecasting)

## Exp 1: Prophet, one model per item and store
WAPE 27%. Training took 9 hours. Dropped.

## Exp 2: LightGBM global model (current model)
WAPE 22%. Trains in 2.5 hours on the 8-core batch server, predicts all stores in 20 minutes. Retrained weekly.

## Exp 3: Temporal Fusion Transformer (deep learning)
WAPE 19% in a 2-week trial on a rented cloud GPU, where training took 4 hours. Estimated more than 30 hours on the CPU batch server. Parked.

## Error analysis on the current model
The largest errors are the first week of Ramadan, salary days, and bakery items on very hot days.

## Ideas not tested yet
Add a daily temperature forecast feature (expected about 1 point lower WAPE). Add "days since Ramadan started" features (expected about 2 points lower WAPE in Ramadan weeks). Both keep the current model and training time.
