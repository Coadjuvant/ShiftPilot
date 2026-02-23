# Shift Scheduler Design

## Core Data Model

### Staff Member
- `id`: unique string.
- `name`: display name.
- `role`: `Tech` | `RN` | `Admin`.
- `can_open`: Tech can work open duty.
- `can_close`: Tech can work close duty.
- `can_bleach`: Tech can take bleach close duty.
- `availability`: day map for `Mon` to `Sat`.
- `preferences` (Tech scoring weights, lower is better):
  - `open_mwf`, `mid_mwf`, `close_mwf`
  - `open_tts`, `mid_tts`, `close_tts`

### Daily Requirement
- `day_name`: `Mon` to `Sat`.
- `patient_count`: integer census input.
- `tech_openers`, `tech_mids`, `tech_closers`: requested Tech slots.
- `rn_count`, `admin_count`: requested RN/Admin slots.

### Config
- Clinic metadata: `clinic_name`, `timezone`, `start_date`, `weeks`.
- Bleach config: `bleach_day`, `bleach_rotation`, `bleach_cursor`, `bleach_frequency`.
- Ratios:
  - `patients_per_tech`
  - `patients_per_rn`
  - `techs_per_rn`
- Constraint sliders (`0` to `10`):
  - `enforce_three_day_cap`
  - `enforce_post_bleach_rest`
  - `enforce_alt_saturdays`
  - `limit_tech_four_days`
  - `limit_rn_four_days`

### PTO
- Flattened entries: `staff_id`, `date`.
- UI supports date ranges; backend consumes per-day records.

## Scheduling Rules

1. Build slots for each day/week in this order:
   - Tech open, Tech mid, Tech close, RN coverage, Admin coverage.
2. Auto-expand demand from ratios:
   - If patient census implies more Techs, add the gap to Tech mids.
   - RN demand is raised to the max of:
     - explicit `rn_count`
     - `ceil(patient_count / patients_per_rn)`
     - `ceil(total_tech_slots / techs_per_rn)`
3. Saturdays force `admin_count = 0`.
4. Tech assignment order and daily rule:
   - Tech `close` and `open` are assigned before Tech `mid` slots.
   - Techs can hold only one labeled duty slot per day (`open`, `mid`, `mid 2`, `close`, `bleach`).
5. Hard eligibility filters:
   - Role match, availability, PTO, open/close permissions, bleach permission.
6. Slider semantics:
   - `10` means hard constraint (cannot be violated).
   - `1..9` means soft penalty added when violated.
   - `0` disables that penalty.
7. If a slot cannot be staffed:
   - Tech open/close: stored as unfilled (`staff_id = null`).
   - Other slots: assigned to `FLOAT`.
   - Each unfilled slot adds fixed penalty `10`.
8. Unfilled slot behavior:
   - If a slot cannot be staffed under constraints, it is assigned to `FLOAT` and the run still completes.
   - Each unfilled/FLOAT slot adds penalty `10`, so tournament selection still prefers runs with fewer gaps.
9. Hard 4-day cap behavior:
   - If Tech or RN 4-day cap slider is `10`, the scheduler should avoid assigning a 5th day for that role.
   - If demand cannot be satisfied under hard constraints, remaining non-critical slots fall back to `FLOAT`/unfilled handling.

## Scoring Model

- Lower is better.
- For scored roles, candidate score is:
  - preference penalty
  - plus soft constraint penalties (`1..9`)
  - plus fairness penalty (`FAIRNESS_WEIGHT * current_assignments`).
- Hard violations (`10`) are filtered out before scoring.
- Bleach slots also respect rotation and cursor behavior.
- Unfilled slots always add penalty `10`.

## Role Export and Scheduling Scope

- `export_roles` is required when running a schedule.
- If no roles are selected, API returns `400`.
- Selected roles control:
  - which roles are scheduled,
  - which roles are scored,
  - which roles appear in exported output.
- Any role not selected for export is not scheduled.

## Current Stack

- Backend: FastAPI (`backend/api/main.py`) + scheduler engine (`backend/scheduler/engine.py`).
- Frontend: React + TypeScript (`frontend/`).
- Main run endpoint: `POST /schedule/run`.
