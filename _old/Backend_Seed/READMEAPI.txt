
ShiftPilot Backend API (drop-in)
================================

This adds a tiny FastAPI web server on top of the Backend_Seed engine.

Files:
- api_main.py
- requirements_api.txt
- payload.sample.json

Install (from Backend_Seed/):
-----------------------------
pip install -r requirements.txt
pip install -r requirements_api.txt

Run:
----
uvicorn api_main:app --reload

Test it:
--------
# Validate config
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/validate -H "Content-Type: application/json" --data @payload.sample.json

# Generate and download Excel
curl -X POST http://127.0.0.1:8000/generate -H "Content-Type: application/json" --data @payload.sample.json -o schedule_v2.xlsx

What it does:
-------------
- POST /generate: accepts your config + start/weeks/trials (+optional PTO) and returns the Excel file as the response body.
- POST /validate: runs schema validation and returns any errors.
- GET /health: simple health check.

Note:
- Run these commands from the Backend_Seed directory so imports of scheduler_app work.
