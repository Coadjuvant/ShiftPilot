# ShiftPilot User Guide

ShiftPilot helps clinic managers build multi-week staff schedules, enforce clinic rules, and export rosters for downstream tools.

## Quick start

1) Open the site and select `Login`.
2) After login, go to `Planner`.
3) Load a config, update inputs, then run the schedule.

## Planner workflow

### 1) Load or create a config
- Use the config dropdown to load an existing clinic config.
- Update clinic name, staffing, and rules as needed.
- Use `Save` to persist changes.

### 2) Staff
Define your roster (names + roles). This is the pool the scheduler can use.

### 3) Availability
Mark which days each staff member can work.

### 4) Prefs
Set preference weights (what each person prefers to open/close).

### 5) Demand
Define daily demand (how many Tech/RN/Admin slots are needed per day).

### 6) PTO
Add time off for each staff member (single day or ranges).

### 7) Bleach
Set bleach day frequency and the rotation order.
- The rotation advances when the assigned person bleaches.
- If someone is unavailable, they are skipped and placed first in line next time.

### 8) Run
Set the schedule window and constraints, then click `Run Schedule`.
- You can toggle constraints like max days/week, alternate Saturdays, and post-bleach rest.
- If a slot cannot be filled, it will be marked as needing coverage.

## Schedule results

- A schedule matrix appears in the planner after a successful run.
- The latest run is also saved and shown on the home page schedule card (only when logged in).
- Use the week arrows on the home page card to move through the schedule weeks.

## Exports

In the planner:
- `Download Latest Schedule` exports the most recent saved schedule (Excel).
- `Download CSV` exports the most recent saved schedule (CSV).
- `Export roles` controls which roles appear in exports.

## Login behavior

- The top-right button toggles between `Login` and `Logout`.
- Sessions expire; if the session ends, you will be prompted to log in again.

## Admin (optional)

Admins can manage invites, user roles, and review recent activity.

## Support

If you need help, contact: `support@shiftpilot.me`
