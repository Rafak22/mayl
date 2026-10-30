# Engine contract: ticket routing API

## Latency
Under 1 second per ticket at p95. Current: 420 ms.

## Interface
POST /route returns {team, confidence}. Tickets with confidence under 0.6 go to a human triage queue.

## Change history
Jun 2026: switched tokenizer, estimated 1 day, actual 1 day. Aug 2026: added Complaints team class, estimated 2 days, actual 3 days (relabeling).
