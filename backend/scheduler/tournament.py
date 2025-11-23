from __future__ import annotations

from typing import Iterable, Sequence, Tuple, Optional
import random

from .model import StaffMember, DailyRequirement, ScheduleConfig, PTOEntry, ScheduleResult
from .engine import generate_schedule


def run_tournament(
    staff: Sequence[StaffMember],
    requirements: Sequence[DailyRequirement],
    cfg: ScheduleConfig,
    pto_entries: Iterable[PTOEntry] = (),
    *,
    trials: int = 10,
    base_seed: Optional[int] = None,
) -> Tuple[ScheduleResult, int]:
    trials = max(1, trials)
    seed_source = random.Random(base_seed)
    best_result: Optional[ScheduleResult] = None
    best_seed: Optional[int] = None

    for i in range(trials):
        seed = (base_seed + i) if base_seed is not None else seed_source.randrange(1 << 30)
        result = generate_schedule(
            staff,
            requirements,
            cfg,
            pto_entries=pto_entries,
            rng_seed=seed,
        )
        result.seed = seed
        if best_result is None or result.total_penalty < best_result.total_penalty:
            best_result = result
            best_seed = seed

    assert best_result is not None and best_seed is not None
    best_result.seed = best_seed
    return best_result, best_seed
