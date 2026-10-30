# Compliance rules

## Explainability
Every fraud flag shown to an analyst must list its top 3 reasons in plain language. Models that cannot produce per-decision reasons are not allowed in production.

## Audit trail
Every rule change and model change must be recorded with who approved it and why.

## Data residency
Customer transaction data must stay inside the country. No external model APIs may receive raw transaction data.
