# Integration contract: clinic systems

## Calendar API
Endpoints: find_slots(clinic, specialty, date range), book(patient, slot), cancel(booking). No delete. Rate limit 10 requests per second.

## Nurse alert
Emergency or nurse-callback cases are pushed to the nurse station app with the patient's message and the agent's reason. Must arrive within 30 seconds.

## Hosting and data
Runs on the client's in-country cloud. Patient data must not leave the country. Allowed models must run in-region.

## Approved stack
Python 3.11, FastAPI, the clinic's calendar SDK. Every booking action is logged for audit.
