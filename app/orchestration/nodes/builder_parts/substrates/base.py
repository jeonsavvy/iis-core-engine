from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SubstrateProfile:
    substrate_id: str
    camera_model: str
    interaction_model: str
    render_bias: str
    objective_hint: str


Resolver = Callable[[str], SubstrateProfile | None]
