# Engineering change history (actual effort)

## Mar 2026: added device fingerprint feature
Feature builder + scoring service input schema changed. Estimated 3 days, actual 4 days (schema migration took longer).

## May 2026: post-filter rule for salary-day spikes
Added a rule layer after the model in the scoring service. No retraining needed. Estimated 1 day, actual half a day.

## Jul 2026: retrained XGBoost with class weights
Model swap only, same interface. Estimated 2 days, actual 2 days, including shadow testing.

## Aug 2026: reasons format change
Changed reasons from 2 to 3 items. Required dashboard update. Estimated 2 days, actual 3 days.
