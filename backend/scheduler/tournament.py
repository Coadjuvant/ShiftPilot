from __future__ import annotations

from typing import Iterable, Sequence, Tuple, Optional
import random

from .model import StaffMember, DailyRequirement, ScheduleConfig, PTOEntry, ScheduleResult
from .engine import generate_schedule, FixedAssignmentConflict


def run_tournament(
    staff: Sequence[StaffMember],
    requirements: Sequence[DailyRequirement],
    cfg: ScheduleConfig,
    pto_entries: Iterable[PTOEntry] = (),
    *,
    trials: int = 10,
    base_seed: Optional[int] = None,
    scheduled_roles: Optional[Sequence[str]] = None,
    score_roles: Optional[Sequence[str]] = None,
    fixed_assignments: Optional[dict] = None,
) -> Tuple[ScheduleResult, int]:
    trials = max(1, trials)
    seed_source = random.Random(base_seed)
    best_result: Optional[ScheduleResult] = None
    best_seed: Optional[int] = None
    last_conflict = None
    def rank(result: ScheduleResult) -> tuple[int, float]:
        # Never prefer an uncovered slot merely because its small fixed penalty
        # is cheaper than assigning an otherwise eligible, busier staff member.
        gaps = sum(a.staff_id is None or str(a.staff_id).upper() in {"FLOAT", "OPEN"}
                   for a in result.assignments)
        return gaps, result.total_penalty

    for i in range(trials):
        seed = (base_seed + i) if base_seed is not None else seed_source.randrange(1 << 30)
        try:
            result = generate_schedule(
                staff, requirements, cfg, pto_entries=pto_entries, rng_seed=seed,
                scheduled_roles=scheduled_roles, score_roles=score_roles, fixed_assignments=fixed_assignments,
            )
        except FixedAssignmentConflict as exc:
            last_conflict = exc
            continue
        result.seed = seed
        if best_result is None or rank(result) < rank(best_result):
            best_result = result
            best_seed = seed

    if best_result is None or best_seed is None:
        raise FixedAssignmentConflict(f"No candidate satisfied the fixed assignments in {trials} trials. {last_conflict}")
    best_result.seed = best_seed
    return best_result, best_seed
