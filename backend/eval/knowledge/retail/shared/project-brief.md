# Project brief: fresh-food demand forecasting

## Client and goal
Tamr Markets (synthetic client) runs 40 grocery stores in Riyadh, Qassim and the Eastern Province. Every night the system forecasts next-day demand for about 1,800 fresh items (bakery, dairy, produce, meat) in every store. The forecasts feed the ERP, which places supplier orders automatically. Goal: less fresh-food waste without empty shelves.

## Success metrics agreed with the client
Forecast error (WAPE) at most 20% on fresh items (current: 22%). Fresh-food waste down 15% versus last year. Stockouts of staple items under 2% of store-days.

## Data agreement
Loyalty-card data may only be used aggregated per store per day. Customer-level purchase histories must never be used for forecasting, by agreement with the client's legal team.

## Status
Mid-project. The LightGBM model is live in 10 pilot stores; rollout to all 40 stores planned after Ramadan review.
