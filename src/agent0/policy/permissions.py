from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any


class PermissionLevel(IntEnum):
    READ_ONLY = 0
    WORKSPACE_WRITE = 1
    FULL_ACCESS = 2


class Decision(StrEnum):
    SAFE = "safe"
    NEEDS_APPROVAL = "needs_approval"
    FORBIDDEN = "forbidden"


class ApprovalRequired(Exception):
    def __init__(self, tool: str, args: dict[str, Any], reason: str) -> None:
        super().__init__(f"{tool} needs approval: {reason}")
        self.tool = tool
        self.tool_args = args
        self.reason = reason


@dataclass(frozen=True)
class ShellAssessment:
    level: PermissionLevel
    reason: str
    forbidden: bool = False


_READ, _WRITE, _FULL = PermissionLevel.READ_ONLY, PermissionLevel.WORKSPACE_WRITE, PermissionLevel.FULL_ACCESS

_READ_ONLY_COMMANDS = frozenset(
    "ls cat head tail wc grep egrep fgrep rg pwd echo printf date whoami uname env printenv which type file "
    "stat du df tree diff cmp sort uniq cut tr basename dirname realpath readlink sha256sum md5sum jq ps id "
    "hostname true false test [ cd sleep nl column".split()
)
_READ_ONLY_GIT = frozenset(
    "status log diff show rev-parse ls-files blame describe shortlog grep ls-tree cat-file".split()
)
_WRAPPERS = frozenset({"env", "nohup", "time", "command", "nice", "timeout", "exec"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash"})
_ROOT_TARGETS = frozenset(
    {"/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "/home", "/etc", "/usr", "/var", "/bin"}
)
_HALT = frozenset({"shutdown", "reboot", "halt", "poweroff"})
_DISK = frozenset({"fdisk", "parted", "wipefs", "sfdisk", "mkswap"})
_FULL_ACCESS_COMMANDS = frozenset(
    "kill pkill killall docker podman kubectl ssh scp rsync sudo su doas systemctl service mount umount "
    "crontab useradd userdel passwd".split()
)
_PATH_WRITERS = frozenset("touch mkdir tee rmdir truncate".split())
_FORK_BOMB = re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:?\s*&")
_PIPE_TO_SHELL = re.compile(
    r"\b(curl|wget|fetch)\b[^|;&\n]*\|\s*(sudo\s+)?(ba|z|da|k)?sh\b|\b(curl|wget)\b[^|;&\n]*\|\s*(sudo\s+)?(python3?|perl|ruby|node)\b"
)
_SEGMENT_SPLIT = re.compile(r"\|\||&&|[;|\n]|(?<![>&\d])&(?!>)")
_REDIRECT = re.compile(r"(?:^|[^<>&\d])\d?>>?\s*(?!&)([^\s&|;<>]+)")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _outside(path: str, roots: tuple[str, ...]) -> bool:
    p = path.strip("'\"")
    if p in {"/dev/null", "/dev/stdout", "/dev/stderr"}:
        return False
    if p.startswith(("~", "$", "%")):
        return True
    if p.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", p):
        norm = posixpath.normpath(p)
        return not any(norm == r or norm.startswith(r.rstrip("/") + "/") for r in roots)
    return posixpath.normpath(p).startswith("..")


def _flags(args: list[str]) -> tuple[set[str], list[str]]:
    flags: set[str] = set()
    rest: list[str] = []
    for a in args:
        if a.startswith("--"):
            flags.add(a)
        elif a.startswith("-") and len(a) > 1:
            flags.update("-" + c for c in a[1:])
        else:
            rest.append(a)
    return flags, rest


def _skip_flags(args: list[str]) -> list[str]:
    i = 0
    while i < len(args) and (args[i].startswith("-") or _ASSIGN.match(args[i])):
        i += 1
    return args[i:]


def _merge(a: ShellAssessment, b: ShellAssessment) -> ShellAssessment:
    if a.forbidden != b.forbidden:
        return a if a.forbidden else b
    return b if b.level > a.level else a


def _classify_git(args: list[str], roots: tuple[str, ...]) -> ShellAssessment:
    flags, rest = _flags(args)
    sub = next((a for a in args if not a.startswith("-")), "")
    if sub == "push":
        if flags & {"--force", "-f", "--force-with-lease", "--mirror", "--delete"} or any(
            a.startswith("+") for a in rest
        ):
            return ShellAssessment(_FULL, "git force push rewrites remote history")
        return ShellAssessment(_FULL, "git push publishes to a remote")
    if sub == "reset" and "--hard" in flags:
        return ShellAssessment(_FULL, "git reset --hard discards work")
    if sub == "clean" and flags & {"-f", "--force"}:
        return ShellAssessment(_FULL, "git clean deletes untracked files")
    if sub in _READ_ONLY_GIT:
        return ShellAssessment(_READ, "read-only git command")
    if sub in {"branch", "remote", "tag", "config", "stash"} and not (
        flags & {"-d", "-D", "-m", "-M", "--delete", "add", "set-url", "--unset", "--add"} or rest
    ):
        return ShellAssessment(_READ, "read-only git command")
    return ShellAssessment(_WRITE, "modifies the repository")


def _classify_tokens(tokens: list[str], roots: tuple[str, ...], depth: int = 0) -> ShellAssessment:
    while tokens and _ASSIGN.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return ShellAssessment(_READ, "empty command")
    name = posixpath.basename(tokens[0])
    args = tokens[1:]
    flags, rest = _flags(args)

    if name in _WRAPPERS:
        inner = _skip_flags(args)
        if name == "timeout" and inner:
            inner = inner[1:]
        return _classify_tokens(inner, roots, depth) if depth < 5 else ShellAssessment(_FULL, "deeply nested")
    if name in {"sudo", "doas"}:
        inner = _classify_tokens(_skip_flags(args), roots, depth + 1)
        return _merge(ShellAssessment(_FULL, f"{name} runs with elevated privileges"), inner)
    if name in _SHELLS and "-c" in args and args.index("-c") + 1 < len(args):
        return assess_shell(args[args.index("-c") + 1], roots, depth + 1)
    if name in _HALT:
        return ShellAssessment(_FULL, f"{name} stops the machine", forbidden=True)
    if name.startswith("mkfs") or name in _DISK:
        return ShellAssessment(_FULL, f"{name} formats or partitions disks", forbidden=True)
    if name == "dd":
        target = next((a[3:] for a in args if a.startswith("of=")), None)
        if target is not None and target.startswith("/dev/") and target != "/dev/null":
            return ShellAssessment(_FULL, "dd writing to a device", forbidden=True)
        if target is not None and _outside(target, roots):
            return ShellAssessment(_FULL, "dd writes outside the workspace")
        return ShellAssessment(_WRITE, "dd copies data")
    if name == "rm":
        recursive = bool(flags & {"-r", "-R", "--recursive"})
        if recursive and any(t in _ROOT_TARGETS or t.rstrip("/") in _ROOT_TARGETS for t in rest):
            return ShellAssessment(_FULL, "recursive delete of a system or home directory", forbidden=True)
        if any(_outside(t, roots) for t in rest):
            return ShellAssessment(_FULL, "deletes outside the workspace")
        return ShellAssessment(_WRITE, "deletes files in the workspace")
    if name in {"chmod", "chown", "chgrp"}:
        if flags & {"-R", "--recursive"} and any(t.rstrip("/") in {"", "~", "$HOME"} for t in rest[1:]):
            return ShellAssessment(_FULL, f"recursive {name} on a system directory", forbidden=True)
        if any(_outside(t, roots) for t in rest[1:]):
            return ShellAssessment(_FULL, f"{name} outside the workspace")
        return ShellAssessment(_WRITE, f"{name} in the workspace")
    if name == "git":
        return _classify_git(args, roots)
    if name in _FULL_ACCESS_COMMANDS:
        return ShellAssessment(_FULL, f"{name} affects the system or the network")
    if name in {"curl", "wget"}:
        if flags & {"-d", "-F", "-T", "--data", "--data-binary", "--upload-file", "--post-data"} or any(
            a in {"POST", "PUT", "DELETE", "PATCH"} for a in rest
        ):
            return ShellAssessment(_FULL, f"{name} sends data to a remote host")
        return ShellAssessment(_WRITE, f"{name} downloads from the network")
    if name in {"cp", "mv", "ln", "install", "rsync"}:
        if rest and _outside(rest[-1], roots):
            return ShellAssessment(_FULL, f"{name} writes outside the workspace")
        if name == "mv" and any(_outside(t, roots) for t in rest[:-1]):
            return ShellAssessment(_FULL, "mv moves files from outside the workspace")
        return ShellAssessment(_WRITE, f"{name} writes in the workspace")
    if name in _PATH_WRITERS:
        if any(_outside(t, roots) for t in rest):
            return ShellAssessment(_FULL, f"{name} writes outside the workspace")
        return ShellAssessment(_WRITE, f"{name} writes in the workspace")
    if name == "find":
        if flags & {"-delete", "-exec", "-execdir", "-fprint", "-ok"} or any(
            a in {"-delete", "-exec", "-execdir", "-fprint", "-ok"} for a in args
        ):
            return ShellAssessment(_WRITE, "find with side effects")
        return ShellAssessment(_READ, "read-only command")
    if name == "sed" and ("-i" in flags or any(a.startswith("-i") for a in args)):
        return ShellAssessment(_WRITE, "in-place edit")
    if name in {"python", "python3"} and args in (["--version"], ["-V"]):
        return ShellAssessment(_READ, "version check")
    if name in _READ_ONLY_COMMANDS:
        return ShellAssessment(_READ, "read-only command")
    return ShellAssessment(_WRITE, f"{name} may modify the workspace")


def assess_shell(
    cmd: str, workspace_roots: tuple[str, ...] = ("/workspace",), _depth: int = 0
) -> ShellAssessment:
    if _FORK_BOMB.search(cmd):
        return ShellAssessment(_FULL, "fork bomb", forbidden=True)
    if _PIPE_TO_SHELL.search(cmd):
        return ShellAssessment(_FULL, "pipes a remote download into an interpreter", forbidden=True)

    result = ShellAssessment(_READ, "read-only command")
    for segment in _SEGMENT_SPLIT.split(cmd):
        if not segment.strip():
            continue
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            tokens = segment.split()
        seg = _classify_tokens(tokens, workspace_roots, _depth)
        for target in _REDIRECT.findall(segment):
            if target == "/dev/null":
                continue
            if _outside(target, workspace_roots):
                seg = _merge(seg, ShellAssessment(_FULL, "redirects output outside the workspace"))
            else:
                seg = _merge(seg, ShellAssessment(_WRITE, "redirects output to a file"))
        if "$(" in segment or "`" in segment:
            seg = _merge(seg, ShellAssessment(_WRITE, "command substitution"))
        result = _merge(result, seg)
    return result


def classify_shell(
    cmd: str, workspace_roots: tuple[str, ...] = ("/workspace",)
) -> tuple[PermissionLevel, str]:
    a = assess_shell(cmd, workspace_roots)
    return a.level, a.reason


@dataclass
class Policy:
    level: PermissionLevel = PermissionLevel.WORKSPACE_WRITE
    tools: dict[str, Decision] = field(default_factory=dict)
    workspace_roots: tuple[str, ...] = ("/workspace",)

    def decide(self, tool: str, args: dict[str, Any]) -> tuple[Decision, str]:
        override = self.tools.get(tool)
        if override is not None:
            return override, f"policy sets {tool} to {override.value}"
        if tool == "shell":
            a = assess_shell(str(args.get("command", "")), self.workspace_roots)
            if a.forbidden:
                return Decision.FORBIDDEN, a.reason
            if a.level > self.level:
                return Decision.NEEDS_APPROVAL, a.reason
            return Decision.SAFE, a.reason
        if tool in {"read_file", "list_files", "web_fetch"}:
            return Decision.SAFE, "read-only tool"
        if tool == "write_file":
            if self.level >= PermissionLevel.WORKSPACE_WRITE:
                return Decision.SAFE, "workspace write"
            return Decision.NEEDS_APPROVAL, "write requested in read-only mode"
        return Decision.NEEDS_APPROVAL, f"no policy for tool {tool}"
