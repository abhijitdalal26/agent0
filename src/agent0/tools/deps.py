from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent0.core.events import EventSink
from agent0.policy.budget import BudgetMeter
from agent0.policy.permissions import Policy
from agent0.sandbox.base import Sandbox


def call_key(tool: str, args: dict[str, Any]) -> str:
    return f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"


@dataclass
class ToolDeps:
    run_id: str
    sandbox: Sandbox
    events: EventSink
    policy: Policy = field(default_factory=Policy)
    budget: BudgetMeter = field(default_factory=BudgetMeter)
    approved: set[str] = field(default_factory=set)
