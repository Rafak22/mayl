# Engine contract: chatbot service

## Architecture
Channel adapters (app, WhatsApp) → chat API → retriever (hybrid search) → LLM answer → guardrails (price check, sensitive-topic detector) → response or human handover.

## Latency
First token under 2 seconds at p95. Current p95: 1.4 seconds.

## Handover interface
POST /handover sends the full chat transcript and detected intent to the client's contact-centre queue. Agents see the bot's summary first.

## Change history (actual effort)
Jul 2026: added the billing-dispute handover rule. Estimated 1 day, actual 1 day. Aug 2026: added WhatsApp channel. Estimated 5 days, actual 7 days (message template approval delays).
