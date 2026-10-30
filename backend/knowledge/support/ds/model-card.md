# Model card: AraBERT ticket classifier

## Performance
Macro F1 0.88 on 9 teams. Weakest class: Billing vs Payments confusion (F1 0.79).

## Why AraBERT
Chosen over a multilingual model because it handled Gulf dialect better (+6 F1 points in Exp 3).

## Data
48k labeled tickets, normalized (diacritics removed, alef forms unified, emojis mapped to words).
