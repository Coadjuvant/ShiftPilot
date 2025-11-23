# ShiftPilot Backend Seed
- Multi-shift (incl. overnight), multi-openers/closers
- Hard constraints: role, availability, PTO, min rest, max hours/week
- Greedy+tournament scheduler
- Exports: Coverage + Roster (Excel)

Run:
```bash
pip install -r requirements.txt
python -m scheduler_app.cli_v2 --config example.config.v2.json --start 2025-09-22 --weeks 2 --out schedule_v2.xlsx
```
