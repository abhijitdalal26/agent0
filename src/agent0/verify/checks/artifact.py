from __future__ import annotations

import io
import json
import re
from typing import Any

from jsonschema import validators
from PIL import Image, UnidentifiedImageError

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, ConfigError, verdict


def _rules(raw: Any) -> list[tuple[re.Pattern[str], str]]:
    """Accepts `["regex", ...]` or `[{"pattern": "regex", "label": "why"}, ...]`."""
    rules = []
    for item in raw or []:
        if isinstance(item, dict):
            pattern, label = item["pattern"], item.get("label", item["pattern"])
        else:
            pattern = label = str(item)
        rules.append((re.compile(pattern, re.IGNORECASE | re.MULTILINE), label))
    return rules


def _quote(text: str, match: re.Match[str], context: int = 40) -> str:
    start, end = max(0, match.start() - context), min(len(text), match.end() + context)
    snippet = " ".join(text[start:end].split())
    return f"{'…' if start else ''}{snippet}{'…' if end < len(text) else ''}"


class ArtifactCheck:
    """Inspects `config.path` in the sandbox, or `ctx.output` when no path is given."""

    type = CheckType.ARTIFACT
    stage = CheckStage.DETERMINISTIC

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        cfg = criterion.config
        path = cfg.get("path")
        if path:
            if ctx.sandbox is None:
                raise ConfigError("artifact check with a path needs a sandbox")
            try:
                data = await ctx.sandbox.read_file(path)
            except Exception as exc:
                return verdict(criterion, VerdictStatus.FAIL, f"{path} not found or unreadable: {exc}")
            name = path
        else:
            data = ctx.output.encode()
            name = "output"

        problems: list[str] = []
        if "json_schema" in cfg:
            problems += self._json_problems(data, cfg["json_schema"], name)
        if "image" in cfg:
            problems += self._image_problems(data, cfg["image"], name)

        if any(k in cfg for k in ("max_chars", "forbidden_patterns", "required_patterns")):
            text = data.decode("utf-8", errors="replace")
            if (max_chars := cfg.get("max_chars")) is not None and len(text) > int(max_chars):
                problems.append(f"{name} has {len(text)} chars, max is {max_chars}")
            for pattern, label in _rules(cfg.get("forbidden_patterns")):
                for match in pattern.finditer(text):
                    problems.append(f'forbidden ({label}): {match.group(0)!r} in "{_quote(text, match)}"')
            for pattern, label in _rules(cfg.get("required_patterns")):
                if not pattern.search(text):
                    problems.append(f"required ({label}) is missing from {name}")

        if problems:
            return verdict(criterion, VerdictStatus.FAIL, "\n".join(problems))
        return verdict(criterion, VerdictStatus.PASS, f"{name} ok ({len(data)} bytes)")

    @staticmethod
    def _json_problems(data: bytes, schema: dict[str, Any], name: str) -> list[str]:
        try:
            doc = json.loads(data)
        except ValueError as exc:
            return [f"{name} is not valid JSON: {exc}"]
        validator = validators.validator_for(schema)(schema)
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        return [f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors[:5]]

    @staticmethod
    def _image_problems(data: bytes, spec: dict[str, Any], name: str) -> list[str]:
        try:
            with Image.open(io.BytesIO(data)) as img:
                width, height, fmt = img.width, img.height, img.format
        except (UnidentifiedImageError, OSError) as exc:
            return [f"{name} is not a readable image: {exc}"]
        problems = []
        want_w, want_h = spec.get("width"), spec.get("height")
        if (want_w is not None and width != want_w) or (want_h is not None and height != want_h):
            problems.append(f"{name} is {width}x{height}, expected {want_w or '*'}x{want_h or '*'}")
        if (want_fmt := spec.get("format")) and str(want_fmt).upper() != (fmt or "").upper():
            problems.append(f"{name} format is {fmt}, expected {want_fmt}")
        return problems
