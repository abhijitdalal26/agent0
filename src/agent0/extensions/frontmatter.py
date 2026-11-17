from __future__ import annotations

from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            meta = yaml.safe_load("\n".join(lines[1:i])) or {}
            if not isinstance(meta, dict):
                raise ValueError("frontmatter must be a YAML mapping")
            return meta, "\n".join(lines[i + 1 :]).strip()
    raise ValueError("unterminated frontmatter")
