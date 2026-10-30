# Transactions dataset: data dictionary

## Overview
2.1M transfers over 6 months. Fraud rate 0.4%. Labels come from confirmed analyst cases.

## Key columns
sender_id, receiver_id, amount_sar, timestamp, channel (app/web/branch), device_id, receiver_account_age_days, sender_receiver_history_count (number of past transfers between the pair in 6 months).

## Known issues
Family relationship is not labeled directly. sender_receiver_history_count is the best available proxy for known contacts. Salary-day spikes inflate false alarms on the 25th to 28th of each month.
