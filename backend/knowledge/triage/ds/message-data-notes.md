# Patient message data notes (synthetic)

## Overview
12,000 past WhatsApp messages (anonymized), 82% Arabic, 18% English. Reception staff tagged each with an outcome: routine booking, same-day booking, nurse callback, emergency advice, admin question.

## Distribution
Routine booking 58%, admin question 21%, same-day booking 14%, nurse callback 6%, emergency advice 1%.

## Data issues
Emergency examples are rare (about 120 messages), so the urgency classifier needs rule-based safety checks on top. Many messages mix symptoms with booking requests in one sentence, for example "عندي حرارة من ثلاث أيام ابي موعد" (I've had a fever for three days, I want an appointment).
