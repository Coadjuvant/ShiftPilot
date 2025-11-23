ShiftPilot — Combined Package

Includes:
- Brand_Kit/ — logos, icons, color tokens, and a simple hero index.html
- Backend_Seed/ — scheduler engine (multi-shift, overnight, multi-openers/closers) + Excel exports

Quick start (Backend):
1) Open a terminal in Backend_Seed/
2) pip install -r requirements.txt
3) python -m scheduler_app.cli_v2 --config example.config.v2.json --start 2025-09-22 --weeks 2 --out schedule_v2.xlsx

Open schedule_v2.xlsx → Coverage & Roster tabs.
