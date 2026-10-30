# Knowledge base and evaluation set

## Knowledge base contents
312 documents: package catalogue (prepaid, postpaid, data add-ons), roaming prices for 40 countries, billing policies, SIM and eSIM guides, store locations. Arabic and English versions of each. Chunked by section, about 2,400 chunks.

## Evaluation set
600 real-style customer questions (70% Arabic, 30% English) with reference answers, refreshed monthly. 120 questions are in Gulf dialect, for example "ابي باقة انترنت للسفر" (I want a travel data package).

## Latest evaluation (October 2026)
Accuracy 91.2%. Weakest area: roaming questions about countries added last month (84%). Hallucinated prices: 0.3%, all caught by the price-check guardrail.

## Known data issues
Some package names differ between Arabic and English documents (for example "باقة سوا" vs "Sawa Plus"). A synonym list fixes most retrieval misses.
