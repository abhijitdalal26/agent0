import json
import re
from pathlib import Path

import pytest

from agent0.core.types import Task

TASKS = sorted(Path(__file__).parents[1].glob("examples/**/*task*.json"))


@pytest.mark.parametrize("path", TASKS, ids=lambda p: p.name)
def test_example_task_files_parse(path):
    spec = json.loads(path.read_text(encoding="utf-8"))
    task = Task(title=spec["title"], prompt=spec["prompt"], criteria=spec.get("criteria", []))
    for c in task.criteria:
        for key in ("required_patterns", "forbidden_patterns"):
            for pattern in c.get("config", {}).get(key, []):
                re.compile(pattern)


def test_examples_found():
    assert TASKS
