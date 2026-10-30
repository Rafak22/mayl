# Experiment log (PPE)

## Exp 3: YOLOv8n, 640px (current model v3)
mAP50 0.89. Recall for "head" (no helmet) 96%. Fast enough for CPU inference at the edge.

## Exp 4: YOLOv8s, 640px
mAP50 0.91, but 2.3 times slower. Parked because the site edge boxes are CPU-only.

## Error analysis on model v3
Most misses are tiny heads far from the camera. Most "wrong compliant" cases are carried helmets: the model sees a helmet and a head in the same person box and the alert engine counts it as compliant.

## Idea not tested yet
A post-processing rule: a helmet only counts if its box overlaps the top part of the head box. No retraining needed.
