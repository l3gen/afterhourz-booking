"""Service menu. Prices are placeholders, edit them here (changes go through PR review).

All durations must be multiples of SLOT_MINUTES. Money is stored in cents.
"""

from dataclasses import asdict, dataclass

SLOT_MINUTES = 30


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    description: str
    duration_min: int
    price_cents: int
    deposit_cents: int

    def public(self) -> dict:
        return asdict(self)


SERVICES: tuple[Service, ...] = (
    Service("haircut", "Haircut", "Precision cut and fade, finished with a hot towel.", 30, 3500, 1000),
    Service("cut-beard", "Haircut + Beard", "Full cut plus beard shape-up and line.", 60, 5000, 1500),
    Service("kids", "Kids Cut", "Ages 12 and under.", 30, 2500, 1000),
    Service("beard", "Beard Trim", "Trim, shape, and razor line.", 30, 2000, 500),
    Service("lineup", "Line-Up", "Clean edges only.", 30, 1500, 500),
)

_BY_ID = {s.id: s for s in SERVICES}

for _s in SERVICES:  # fail fast on bad catalog edits
    assert _s.duration_min % SLOT_MINUTES == 0, f"{_s.id}: duration must be a multiple of {SLOT_MINUTES}"
    assert 0 <= _s.deposit_cents <= _s.price_cents, f"{_s.id}: deposit must be within price"


def get_service(service_id: str) -> Service | None:
    return _BY_ID.get(service_id)
