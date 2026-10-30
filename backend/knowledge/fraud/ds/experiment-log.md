# Experiment log

## Exp 7: XGBoost, class weights (current production candidate)
Recall 91%, false alarm rate 8.3%. Main false-alarm source: repeated transfers to the same receivers around salary day.

## Exp 9: graph neural network on transfer network
Recall 94% offline, but no per-decision explanations and needs PyTorch. Parked because of compliance and engine contract.

## Exp 10: post-filter on known contacts (offline test)
Down-ranking known-contact transfers under SAR 50k cut false alarms by 28% with no measurable recall loss.
