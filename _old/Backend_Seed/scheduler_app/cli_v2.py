
from __future__ import annotations
import argparse
from datetime import datetime
from scheduler_app.config.loader_v2 import load_config
from scheduler_app.engine.generate_v2 import tournament
from scheduler_app.engine.verify_v2 import verify
from scheduler_app.engine.local_search import improve_by_swaps
from scheduler_app.io.export_v2 import export_excel

def main(argv=None):
    p = argparse.ArgumentParser(description="ShiftPilot Scheduler v2 (backend seed + local search)")
    p.add_argument("--config","-c", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--weeks", type=int, default=2)
    p.add_argument("--pto", type=str, default=None)
    p.add_argument("--trials", type=int, default=40)
    p.add_argument("--improve-swaps", type=int, default=0, help="Optional local search swap iterations")
    p.add_argument("--out", type=str, default="schedule_v2.xlsx")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    result = tournament(cfg, start, args.weeks, args.pto, trials=args.trials)
    if not result: raise SystemExit("Failed to generate any schedule")
    assignments, seed, sc = result

    if args.improve_swaps and args.improve_swaps > 0:
        assignments, sc2, accepted = improve_by_swaps(assignments, cfg, iterations=args.improve_swaps)
        print(f"Local search accepted {accepted} swaps. Score: {sc:.2f} -> {sc2:.2f}")
        sc = sc2

    issues = verify(assignments, cfg["constraints"]["min_rest_hours"])
    if issues:
        print("Verification issues:"); [print(" -", i) for i in issues]
    else:
        print("No violations detected.")
    id2name = {s["id"]: s["name"] for s in cfg["staff"]}
    export_excel(assignments, id2name, args.out)
    print(f"Wrote {args.out}. Best seed={seed} score={sc:.2f}")

if __name__ == "__main__":
    main()
