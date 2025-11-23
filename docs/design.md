# Shift Scheduler Design

## Entities

### StaffMember
- `id`: unique string
- `name`: display name
- `role`: `Tech` \| `RN` \| `Admin`
- `can_open`: bool
- `can_close`: bool
- `can_bleach`: bool (Tech only)
- `availability`: dict[str → bool] for days `Mon` … `Sat`
- `preferences`:
  - `open_weight`: float (MWF)
  - `open_weight_tts`: float (TTS)
  - `close_weight`: float (MWF)
  - `close_weight_tts`: float (TTS)
  - `mid_weight`: float (MWF)
  - `mid_weight_tts`: float (TTS)

### ClinicDemand
- `day`: `Mon` … `Sat`
- `patient_count`: int (for deriving Tech/RN minimums)
- `required_slots`:
  - `openers`: int (<= 2)
  - `mids`: int (>= 0)
  - `closers`: int (>= 0)

### Config
- `clinic_name`
- `timezone`
- `bleach_day`: `Mon` … `Sat`
- `bleach_rotation`: list of staff ids
- `bleach_cursor`: next index (0-based)
- `constraints` (toggle-able):
  - `enforce_three_day_cap`: bool (no 3 consecutive work days)
  - `enforce_post_bleach_rest`: bool (no shift day after bleaching)
  - `enforce_alt_saturdays`: bool (no consecutive Saturdays)
- `ratios`:
  - `patients_per_tech`: default 4
  - `patients_per_rn`: default 12
  - `techs_per_rn`: default 4

### PTO
- records with `staff_id`, `date`
- support range upload (expand to list of dates)

## Scheduling Notes

1. Build daily slot list (openers, mids, closers) respecting required counts.
2. Determine minimum Tech/RN counts using ratios and patient totals.
3. Assign bleach slot: on `bleach_day`, select next eligible closer (`can_bleach` & `can_close`).
4. Search strategy:
   - Start with greedy assignment ordered by day/role.
   - Score = weighted sum of preference penalties + fairness penalty for uneven Tech distribution.
   - Local improvement via hill-climb swap among same-role slots.
5. Constraints enforced hard:
   - Availability, PTO exclusion, ratio minimums, bleach requirement.
6. Optional constraints applied when toggled.

## Outputs

- `schedule.xlsx` with sheets:
  - Coverage (counts per day/role)
  - Roster (rows: day, role, staff, duty)
  - Summary (per staff totals, bleach count)

## Modernized Architecture (2025-11-21)

The Streamlit prototype remains in `UI/app.py`, but the long-term product will move to a FastAPI + React stack:

- **FastAPI** (`backend/api/main.py`): exposes `/health` and `/schedule/run`. The API wraps the existing scheduler engine so clinics or external tools can request rosters programmatically. Add new endpoints here as more config surfaces.
- **React (Vite + TypeScript)** (`frontend/`): owns UI state locally. The prototype `StaffPlanner` page demonstrates the non-resetting editor behavior that motivated the migration. Eventually each Streamlit tab will be rebuilt as isolated React routes/components backed by the API.

Workflow:

1. Run the API with `uvicorn backend.api.main:app --reload`.
2. Install frontend deps (`npm install` inside `frontend/`) and start the dev server (`npm run dev`). Vite proxies `/api/*` calls to the FastAPI server for local development.
3. When features reach parity, retire the Streamlit UI and package the React app via WebView2/Electron for distributable desktop builds.
