# Engine contract: nightly forecast batch

## Pipeline
Point-of-sale data loads at 02:00 → feature build (about 1.5 hours) → prediction (20 minutes) → order guardrails → ERP export → dashboard refresh. Runs on Airflow.

## Batch window
The nightly batch must finish by 06:00 so store managers can review forecasts at 07:00 and the ERP upload is done by 11:00. It currently finishes at about 05:30.

## Hardware
One 8-core CPU server, no GPU. The weekly retraining runs separately on Friday afternoons when the server is idle.

## ERP interface
One CSV file per store with item, date and forecast quantity. Changing the CSV columns needs a change from the ERP vendor, with about 2 weeks lead time.
