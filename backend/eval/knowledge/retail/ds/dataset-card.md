# Dataset card: store sales

## Sources
3 years of daily sales from the point-of-sale system: 40 stores, about 1,800 fresh items. Promotions calendar from the ERP. Hijri and Gregorian holiday calendar. Loyalty-card totals aggregated per store per day.

## Known data issues
Days when an item was out of stock are recorded as zero sales (about 4% of store-days), which hides real demand. These days are masked during training. Store 31 opened in August 2026 and has less than 3 months of history.

## Features (current pipeline)
Lagged sales (7, 14, 28 days), day of week, Hijri calendar flags (Ramadan, Eid), salary-day flag, promotion flag and discount depth.
