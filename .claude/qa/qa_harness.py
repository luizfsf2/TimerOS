#!/usr/bin/env python3
"""Deterministic support harness for the project's single QA role.

The harness owns only mechanical QA operations. It never creates the functional
QA_ID, never decides functional verdicts, and never writes outside .tmp/qa/.
Workspace isolation is by front_id (front_key == front_id), not by Git branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = ROOT / ".tmp" / "qa"
QA_CONTRACT_VERSION = "H2.5.3"
SAFE_FRONT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_BLOCK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_WINDOWS_NATIVE_EXTENSIONS = {".com", ".exe"}
_WINDOWS_BATCH_EXTENSIONS = {".bat", ".cmd"}
_WINDOWS_EXECUTABLE_EXTENSIONS = (
    _WINDOWS_NATIVE_EXTENSIONS | _WINDOWS_BATCH_EXTENSIONS
)
_DEFAULT_WINDOWS_PATHEXT = ".COM;.EXE;.BAT;.CMD"

QA_RELEVANT_PREFIXES = (
    "backend/",
    "frontend/",
    "tests/",
    "migrations/",
    "scripts/",
    "alembic/",
    "config/",
)
QA_RELEVANT_EXACT_FILES = {
    ".claude/qa/qa_harness.py",
    ".claude/commands/qa.md",
}
QA_RELEVANT_ROOT_FILES = {
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "config.yaml",
    "app.yaml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _is_qa_ephemeral_path(path: str) -> bool:
    return path.startswith(".tmp/qa/")


def validate_front_id(front_id: str) -> str:
    if front_id in {".", ".."} or not SAFE_FRONT_ID.fullmatch(front_id):
        raise ValueError(
            "front_id must be a safe single path segment using only "
            "letters, digits, dot, underscore or hyphen"
        )
    return front_id


def front_key_from(front_id: str) -> str:
    return validate_front_id(front_id)


def validate_block_id(block_id: str) -> str:
    if block_id in {".", ".."} or not SAFE_BLOCK_ID.fullmatch(block_id):
        raise ValueError(
            "block id must be a safe single path segment using only "
            "letters, digits, dot, underscore or hyphen"
        )
    return block_id


def _status_path(path: str) -> str:
    return path.split(" -> ")[-1].replace("\\", "/")


def _is_qa_relevant_path(path: str) -> bool:
    normalized = _status_path(path)
    if _is_qa_ephemeral_path(normalized):
        return False
    if normalized in QA_RELEVANT_ROOT_FILES or normalized in QA_RELEVANT_EXACT_FILES:
        return True
    return normalized.startswith(QA_RELEVANT_PREFIXES)


def _relevant_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if _is_qa_relevant_path(path)]


def _relevant_dirty_fingerprint() -> list[dict[str, str | None]]:
    """Snapshot QA-relevant dirty state, including file content."""
    lines = git("status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()
    fingerprint: list[dict[str, str | None]] = []
    for line in lines:
        if not line:
            continue
        path = _status_path(line[3:].strip())
        if not _is_qa_relevant_path(path):
            continue

        absolute = ROOT / path
        digest: str | None = None
        if absolute.is_symlink():
            try:
                digest = f"symlink:{os.readlink(absolute)}"
            except OSError:
                digest = "symlink:<unreadable>"
        elif absolute.is_file():
            try:
                digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
            except OSError:
                digest = "<unreadable>"

        fingerprint.append(
            {
                "status": line[:2],
                "path": path,
                "sha256": digest,
            }
        )

    return sorted(
        fingerprint,
        key=lambda item: (
            item["path"] or "",
            item["status"] or "",
            item["sha256"] or "",
        ),
    )


def _dirty_changed_paths(
    before: list[dict[str, str | None]],
    after: list[dict[str, str | None]],
) -> list[str]:
    before_by_path = {str(item.get("path")): item for item in before}
    after_by_path = {str(item.get("path")): item for item in after}
    return sorted(
        path
        for path in set(before_by_path) | set(after_by_path)
        if before_by_path.get(path) != after_by_path.get(path)
    )


def validate_qa_id(front_id: str, qa_id: str) -> None:
    pattern = re.compile(rf"^QA-{re.escape(front_id)}-(\d{{3,}})$")
    if not pattern.fullmatch(qa_id):
        raise ValueError(
            f"qa_id must match QA-{front_id}-<NNN> with a numeric 3+ digit suffix"
        )




PACKAGE_DRIVE_DOMAIN_RE = re.compile(r"(?i)\b(?:drive|docs)\.google\.com\b")
PACKAGE_DRIVE_ID_FIELD_RE = re.compile(
    r"(?im)^\s*(?:GOOGLE_)?DRIVE(?:_(?:FILE|FOLDER))?_?ID\s*:\s*\S+\s*$"
    r"|^\s*(?:PACOTE_QA|RELATORIO_QA)_(?:URL|ID)\s*:\s*\S+\s*$"
)
PACKAGE_DRIVE_ACTION_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:upload|publique|publicar|envie|enviar|grave|gravar|copie|copiar|"
    r"sincronize|sincronizar|abra|abrir|acesse|acessar|leia|ler)\b"
    r".{0,120}\b(?:google\s+drive|drive)\b"
    r"|\b(?:google\s+drive|drive)\b.{0,120}"
    r"\b(?:upload|publique|publicar|envie|enviar|grave|gravar|copie|copiar|"
    r"sincronize|sincronizar|abra|abrir|acesse|acessar|leia|ler)\b"
    r")"
)
PACKAGE_DRIVE_NEGATION_RE = re.compile(
    r"(?i)\b(?:n[aã]o|nunca|never|do\s+not|don't|sem)\b"
)


def _package_field_values(package_text: str, field: str) -> list[str]:
    pattern = re.compile(
        rf"(?im)^\s*{re.escape(field)}\s*:\s*(.*?)\s*$"
    )
    return [match.group(1).strip() for match in pattern.finditer(package_text)]


def validate_package_text(package_text: str, front_id: str, qa_id: str) -> list[str]:
    """Return deterministic handoff-contract violations found in a QA package."""
    front_key = front_key_from(front_id)
    validate_qa_id(front_id, qa_id)
    issues: list[str] = []

    def single_field(field: str) -> str | None:
        values = _package_field_values(package_text, field)
        if not values:
            issues.append(f"missing required field: {field}")
            return None
        if len(values) != 1:
            issues.append(f"field must appear exactly once: {field}")
            return None
        return values[0]

    contract_version = single_field("QA_CONTRACT_VERSION")
    package_qa_id = single_field("QA_ID")
    package_front_id = single_field("front_id")
    mode = single_field("MODO")
    result_destination = single_field("RESULT_DESTINATION")

    if contract_version is not None and contract_version != QA_CONTRACT_VERSION:
        issues.append(
            "QA_CONTRACT_VERSION must match local harness version "
            f"({QA_CONTRACT_VERSION})"
        )
    if package_qa_id is not None and package_qa_id != qa_id:
        issues.append(f"QA_ID must be exactly {qa_id}")
    if package_front_id is not None and package_front_id != front_id:
        issues.append(f"front_id must be exactly {front_id}")
    if mode is not None and mode not in {"APOIO", "FORMAL"}:
        issues.append("MODO must be APOIO or FORMAL")
    expected_destination = f".tmp/qa/{front_key}/result/"
    if result_destination is not None:
        normalized_destination = result_destination.replace("\\", "/")
        if normalized_destination != expected_destination:
            issues.append(
                "RESULT_DESTINATION must be local and exactly "
                f"{expected_destination}"
            )

    if PACKAGE_DRIVE_DOMAIN_RE.search(package_text):
        issues.append(
            "Google Drive URLs/domains are forbidden inside the executable QA package"
        )
    if PACKAGE_DRIVE_ID_FIELD_RE.search(package_text):
        issues.append(
            "Google Drive IDs/URL fields are forbidden inside the executable QA package"
        )

    for line_number, line in enumerate(package_text.splitlines(), start=1):
        if (
            PACKAGE_DRIVE_ACTION_RE.search(line)
            and not PACKAGE_DRIVE_NEGATION_RE.search(line)
        ):
            issues.append(
                "operational instruction depends on Google Drive "
                f"(line {line_number})"
            )
            break

    return issues


def cmd_validate_package(args: argparse.Namespace) -> int:
    _front_key(args)
    validate_qa_id(args.front_id, args.qa_id)

    package_path = Path(args.package_file).expanduser()
    if not package_path.is_absolute():
        package_path = ROOT / package_path

    try:
        package_text = package_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        print(f"BLOCKED: cannot read QA package: {exc}")
        return 1
    except UnicodeError as exc:
        print(f"BLOCKED: QA package is not valid UTF-8 text: {exc}")
        return 1

    issues = validate_package_text(package_text, args.front_id, args.qa_id)
    print_kv("package_file", str(package_path))
    print_kv("front_id", args.front_id)
    print_kv("qa_id", args.qa_id)

    if issues:
        print_kv("package_guard", "BLOCKED")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print_kv("package_guard", "PASS")
    print_kv(
        "result_destination",
        f".tmp/qa/{front_key_from(args.front_id)}/result/",
    )
    return 0


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def current_branch() -> str:
    return git("branch", "--show-current").stdout.strip()


def current_head() -> str:
    return git("rev-parse", "HEAD").stdout.strip()


def status_porcelain() -> tuple[list[str], list[str]]:
    """Return (tracked_dirty_paths, untracked_paths)."""
    lines = git("status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()
    tracked, untracked = [], []
    for line in lines:
        if not line:
            continue
        if line.startswith("??"):
            untracked.append(line[3:].strip())
        else:
            tracked.append(line[3:].strip())
    return tracked, untracked


def front_dir(front_key: str) -> Path:
    return QA_ROOT / front_key


def state_path(front_key: str) -> Path:
    return front_dir(front_key) / "state.json"


def load_state(front_key: str) -> dict:
    path = state_path(front_key)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(front_key: str, state: dict) -> None:
    path = state_path(front_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def is_ignored(relative_path: str) -> bool:
    result = git("check-ignore", "-q", relative_path)
    return result.returncode == 0


def print_kv(label: str, value: object) -> None:
    print(f"{label}: {value}")


def _front_key(args: argparse.Namespace) -> str:
    return front_key_from(args.front_id)


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------


def _remote_relation(
    branch: str,
    head: str,
) -> tuple[str | None, str | None, str, int | None, int | None]:
    if not branch:
        return None, None, "NO_BRANCH", None, None

    remote_ref = f"origin/{branch}"
    rp = git("rev-parse", "--verify", remote_ref)
    if rp.returncode != 0:
        return remote_ref, None, "NO_REMOTE", None, None

    remote_head = rp.stdout.strip()
    if remote_head == head:
        return remote_ref, remote_head, "EQUAL", 0, 0

    merge_base_result = git("merge-base", "HEAD", remote_ref)
    merge_base = (
        merge_base_result.stdout.strip()
        if merge_base_result.returncode == 0
        else ""
    )
    if merge_base == head:
        relation = "BEHIND_FF"
    elif merge_base == remote_head:
        relation = "AHEAD"
    else:
        relation = "DIVERGED"

    ahead_count = int(
        git("rev-list", "--count", f"{remote_ref}..HEAD").stdout.strip() or 0
    )
    behind_count = int(
        git("rev-list", "--count", f"HEAD..{remote_ref}").stdout.strip() or 0
    )
    return remote_ref, remote_head, relation, ahead_count, behind_count


def cmd_preflight(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    branch_before = current_branch()
    head_before = current_head()
    operation_log: list[str] = []

    fetch_result = git("fetch", "--prune", "origin")
    operation_log.append(
        "$ git fetch --prune origin\n"
        f"{fetch_result.stdout}{fetch_result.stderr}"
    )

    verdict = "PROCEED"
    case = "OK"
    next_action = "checkout ready for QA"
    did_switch = False
    did_ff = False
    switch_from = None
    pull_from = None

    if fetch_result.returncode != 0:
        verdict = "OPERATOR_ACTION_REQUIRED"
        case = "FETCH_FAILED"
        next_action = (
            "git fetch --prune origin failed; resolve the Git problem with the "
            "operator in this local QA session, then rerun preflight"
        )

    if verdict == "PROCEED" and args.expect_branch:
        branch_now = current_branch()
        if branch_now != args.expect_branch:
            switch_from = branch_now
            switch_result = git("switch", args.expect_branch)
            operation_log.append(
                f"$ git switch {args.expect_branch}\n"
                f"{switch_result.stdout}{switch_result.stderr}"
            )
            if switch_result.returncode != 0:
                verdict = "OPERATOR_ACTION_REQUIRED"
                case = "SWITCH_FAILED"
                next_action = (
                    f"could not switch from {branch_now or '<detached>'} to "
                    f"{args.expect_branch}; resolve the Git problem with the "
                    "operator in this local QA session, then rerun preflight"
                )
            else:
                did_switch = True

    branch = current_branch()
    head = current_head()
    remote_ref = None
    remote_head = None
    relation = "UNKNOWN"
    ahead_count = behind_count = None

    if verdict == "PROCEED":
        (
            remote_ref,
            remote_head,
            relation,
            ahead_count,
            behind_count,
        ) = _remote_relation(branch, head)

        if relation == "DIVERGED":
            verdict = "OPERATOR_ACTION_REQUIRED"
            case = "DIVERGED"
            next_action = (
                f"HEAD and {remote_ref} diverged; do not merge/rebase/reset "
                "automatically. Ask the operator in this local QA session."
            )
        elif relation == "BEHIND_FF":
            pull_from = head
            pull_result = git("pull", "--ff-only", "origin", branch)
            operation_log.append(
                f"$ git pull --ff-only origin {branch}\n"
                f"{pull_result.stdout}{pull_result.stderr}"
            )
            if pull_result.returncode != 0:
                verdict = "OPERATOR_ACTION_REQUIRED"
                case = "PULL_FAILED"
                next_action = (
                    "git pull --ff-only failed. Do not clean/reset/rebase "
                    "automatically; resolve the Git problem with the operator in "
                    "this local QA session, then rerun preflight."
                )
            else:
                did_ff = True
                head = current_head()
                (
                    remote_ref,
                    remote_head,
                    relation,
                    ahead_count,
                    behind_count,
                ) = _remote_relation(branch, head)
                case = "FAST_FORWARDED"
                next_action = f"fast-forward applied: {pull_from} -> {head}"
        elif relation == "AHEAD":
            case = "AHEAD"
            next_action = (
                "local branch is ahead of origin; QA will run on the local HEAD"
            )
        elif relation == "NO_REMOTE":
            case = "NO_REMOTE"
            next_action = (
                "no matching origin branch was found; QA will run on the local HEAD"
            )
        elif did_switch:
            case = "SWITCHED"
            next_action = f"switched to {branch}; checkout ready for QA"

    branch = current_branch()
    head = current_head()
    tracked_dirty, untracked = status_porcelain()
    dirty_fingerprint = _relevant_dirty_fingerprint()
    diff_stat = git("diff", "--stat").stdout.strip()
    diff_cached_names = git("diff", "--cached", "--name-only").stdout.splitlines()
    tracked_dirty_relevant = _relevant_paths(tracked_dirty)
    untracked_relevant = _relevant_paths(untracked)
    expected_head_match = args.expect_head is None or head == args.expect_head

    if verdict == "PROCEED" and not expected_head_match:
        next_action += (
            f"; package expected HEAD {args.expect_head} is reference only; "
            f"effective QA target is {head}"
        )

    fdir = front_dir(front_key)
    (fdir / "logs").mkdir(parents=True, exist_ok=True)
    preflight_data = {
        "qa_contract_version": QA_CONTRACT_VERSION,
        "front_id": args.front_id,
        "front_key": front_key,
        "branch_before": branch_before,
        "head_before": head_before,
        "branch": branch,
        "head": head,
        "remote_ref": remote_ref,
        "remote_head": remote_head,
        "relation": relation,
        "ahead_count": ahead_count,
        "behind_count": behind_count,
        "expect_branch": args.expect_branch,
        "expect_head": args.expect_head,
        "expected_head_match": expected_head_match,
        "did_switch": did_switch,
        "switch_from": switch_from,
        "did_ff": did_ff,
        "pull_from": pull_from,
        "tracked_dirty": tracked_dirty,
        "tracked_dirty_relevant": tracked_dirty_relevant,
        "untracked": untracked,
        "untracked_relevant": untracked_relevant,
        "diff_cached_names": diff_cached_names,
        "dirty_fingerprint": dirty_fingerprint,
        "case": case,
        "verdict": verdict,
        "fetch_ok": fetch_result.returncode == 0,
    }
    (fdir / "logs" / "preflight.log").write_text(
        "\n\n".join(operation_log)
        + "\n\n$ git status --porcelain=v1 --untracked-files=all\n"
        + git("status", "--porcelain=v1", "--untracked-files=all").stdout
        + "\n$ git diff --stat\n"
        + diff_stat
        + "\n",
        encoding="utf-8",
    )
    state = load_state(front_key)
    state["preflight"] = preflight_data
    save_state(front_key, state)

    print_kv("qa_contract_version", QA_CONTRACT_VERSION)
    print_kv("front_id", args.front_id)
    print_kv("front_key", front_key)
    print_kv("branch_before", branch_before or "<detached>")
    print_kv("head_before", head_before)
    print_kv("branch", branch or "<detached>")
    print_kv("head", head)
    print_kv("remote_ref", remote_ref or "N/A")
    print_kv("remote_head", remote_head or "N/A")
    print_kv("relation", relation)
    if ahead_count is not None:
        print_kv("ahead/behind", f"{ahead_count}/{behind_count}")
    print_kv("expected_head", args.expect_head or "N/A")
    print_kv("expected_head_match", expected_head_match)
    print_kv("tracked_dirty_relevant", tracked_dirty_relevant or "none")
    print_kv("untracked_relevant", untracked_relevant or "none")
    print_kv("dirty_is_blocking", False)
    print_kv("did_switch", did_switch)
    print_kv("did_ff", did_ff)
    print_kv("case", case)
    print_kv("verdict", verdict)
    print_kv("next_action", next_action)
    print_kv("state_file", str(state_path(front_key)))

    return 0 if verdict == "PROCEED" else 1


# ---------------------------------------------------------------------------
# workspace
# ---------------------------------------------------------------------------


def cmd_workspace(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    validate_qa_id(args.front_id, args.qa_id)

    if not is_ignored(".tmp/qa/probe"):
        print("BLOCKED: .tmp is not ignored by Git.")
        print("Solution: add .tmp/ to the project ignore mechanism outside QA.")
        return 1

    fdir = front_dir(front_key)
    if fdir.exists() and fdir.is_symlink():
        print(f"BLOCKED: {fdir} is a symlink. Do not proceed.")
        return 1

    previous_state = load_state(front_key)

    if args.no_clean:
        if not previous_state:
            print("BLOCKED: --no-clean requested but no state.json exists.")
            return 1
        if previous_state.get("qa_id") != args.qa_id:
            print(
                "BLOCKED: --no-clean QA_ID differs from existing round: "
                f"{previous_state.get('qa_id')}"
            )
            return 1
        report_path = fdir / "result" / "REPORT.md"
        if not report_path.exists():
            print("BLOCKED: --no-clean requested but REPORT.md is missing.")
            return 1
        print_kv("qa_id", args.qa_id)
        print_kv("front_id", args.front_id)
        print_kv("mode", "no-clean")
        print_kv("front_dir", str(fdir))
        return 0

    preflight = previous_state.get("preflight")
    if not preflight or preflight.get("verdict") != "PROCEED":
        print(
            "OPERATOR_ACTION_REQUIRED: workspace starts only after a successful "
            "preflight. Resolve setup in this local QA session and rerun preflight."
        )
        return 1

    preflight_log_path = fdir / "logs" / "preflight.log"
    try:
        preflight_log = (
            preflight_log_path.read_text(encoding="utf-8")
            if preflight_log_path.exists()
            else None
        )
    except OSError:
        preflight_log = None

    if fdir.exists():
        shutil.rmtree(fdir)
    (fdir / "result").mkdir(parents=True, exist_ok=True)
    (fdir / "logs").mkdir(parents=True, exist_ok=True)
    if preflight_log is not None:
        (fdir / "logs" / "preflight.log").write_text(
            preflight_log,
            encoding="utf-8",
        )

    branch = current_branch()
    head = current_head()
    report_path = fdir / "result" / "REPORT.md"
    sync_text = "NÃO"
    if preflight.get("did_switch") or preflight.get("did_ff"):
        parts = []
        if preflight.get("did_switch"):
            parts.append(
                f"switch {preflight.get('switch_from') or '<detached>'} -> {branch}"
            )
        if preflight.get("did_ff"):
            parts.append(f"ff {preflight.get('pull_from')} -> {head}")
        sync_text = "; ".join(parts)

    report_path.write_text(
        "# Relatório de QA\n\n"
        "Status: EM_EXECUCAO\n\n"
        "## 1. Contexto\n\n"
        f"- QA_ID: {args.qa_id}\n"
        f"- Front ID: {args.front_id}\n"
        f"- QA_CONTRACT_VERSION: {QA_CONTRACT_VERSION}\n"
        f"- Branch: {branch}\n"
        f"- HEAD local inicial: {head}\n"
        f"- HEAD esperado no pacote: {preflight.get('expect_head') or 'N/A'}\n"
        f"- HEAD remoto observado: {preflight.get('remote_head') or 'N/A'}\n"
        f"- Commit efetivamente testado: {head}\n"
        f"- Preparação Git realizada: {sync_text}\n",
        encoding="utf-8",
    )

    state = {
        "qa_contract_version": QA_CONTRACT_VERSION,
        "front_id": args.front_id,
        "front_key": front_key,
        "qa_id": args.qa_id,
        "branch": branch,
        "head_initial": head,
        "blocks": {},
        "preflight": preflight,
    }
    save_state(front_key, state)

    print_kv("qa_contract_version", QA_CONTRACT_VERSION)
    print_kv("qa_id", args.qa_id)
    print_kv("front_id", args.front_id)
    print_kv("front_key", front_key)
    print_kv("result_dir", str(fdir / "result"))
    print_kv("report_md", str(report_path))
    print_kv("tmp_ignored", True)
    return 0


# ---------------------------------------------------------------------------
# delta
# ---------------------------------------------------------------------------


def cmd_delta(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    diff = git("diff", "--name-only", f"{args.from_ref}..{args.to_ref}", "--", "*.py")
    if diff.returncode != 0:
        print(f"BLOCKED: git diff falhou: {diff.stderr.strip()}")
        return 1
    files = [f for f in diff.stdout.splitlines() if f and (ROOT / f).exists()]

    bdir = front_dir(front_key)
    bdir.mkdir(parents=True, exist_ok=True)
    out_path = bdir / "delta_py_files.txt"
    out_path.write_text(
        "\n".join(files) + ("\n" if files else ""), encoding="utf-8", newline="\n"
    )

    print_kv("from", args.from_ref)
    print_kv("to", args.to_ref)
    print_kv("existing_py_files", len(files))
    print_kv("out_file", str(out_path))
    if args.print_list:
        for f in files:
            print(f"  {f}")
    return 0


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

_PYTEST_SUMMARY_RE = re.compile(
    r"(\d+) passed|(\d+) failed|(\d+) error|(\d+) skipped|(\d+) xfailed|(\d+) xpassed"
)
_PYTEST_FAILED_LINE_RE = re.compile(r"^FAILED (\S+)")
_RUFF_FINDING_RE = re.compile(r"^\S+\.py:\d+:\d+: \w+\d*")


def _looks_like_pytest(cmd: list[str]) -> bool:
    return any("pytest" in part for part in cmd)


def _looks_like_ruff(cmd: list[str]) -> bool:
    return any("ruff" in part for part in cmd)


_PYTEST_PROGRESS_LINE_RE = re.compile(r"^([.\sFEsxXuq]*)\[\s*\d+%\]\s*$")


def _tally_progress_chars(lines: list[str]) -> str | None:
    """Fallback when the final 'N passed in Ys' line is absent.

    Some environments (observed here: pytest on Git Bash/Windows, non-tty
    stdout) never print the trailing summary line, only the dot/letter
    progress indicator. Tally those characters instead of reporting nothing.
    """
    counts: dict[str, int] = {}
    for line in lines:
        m = _PYTEST_PROGRESS_LINE_RE.match(line)
        if not m:
            continue
        for ch in re.sub(r"\s", "", m.group(1)):
            counts[ch] = counts.get(ch, 0) + 1
    if not counts:
        return None
    label = {
        ".": "passed",
        "F": "failed",
        "E": "error",
        "s": "skipped",
        "x": "xfailed",
        "X": "xpassed",
    }
    parts = [f"{n} {label.get(ch, ch)}" for ch, n in counts.items()]
    return ", ".join(parts) + " (tally aproximado via progress chars; linha final ausente)"


def _summarize_pytest(output: str) -> list[str]:
    lines = output.splitlines()
    summary_line = ""
    for line in reversed(lines):
        if re.search(r"\d+ (passed|failed|error)", line):
            summary_line = line.strip(" =")
            break
    if not summary_line:
        summary_line = _tally_progress_chars(lines) or ""
    failed = [
        m.group(1) for m in (_PYTEST_FAILED_LINE_RE.match(line) for line in lines) if m
    ]
    out = [f"pytest summary: {summary_line or '(nao encontrado)'}"]
    if failed:
        shown = failed[:15]
        out.append(f"FAILED ({len(failed)} total):")
        out.extend(f"  {f}" for f in shown)
        if len(failed) > len(shown):
            out.append(f"  ... e mais {len(failed) - len(shown)} omitidos")
        # first traceback block: from first "____ " header to next "____ " or short summary
        try:
            start = next(
                i for i, line in enumerate(lines) if re.match(r"^_{5,} .+ _{5,}$", line)
            )
            end = next(
                (
                    i
                    for i in range(start + 1, len(lines))
                    if re.match(r"^_{5,} .+ _{5,}$", lines[i])
                    or "short test summary info" in lines[i]
                ),
                min(start + 40, len(lines)),
            )
            out.append("Primeiro traceback util:")
            out.extend(f"  {line}" for line in lines[start:end][:40])
        except StopIteration:
            pass
    return out


def _summarize_ruff(output: str) -> list[str]:
    lines = output.splitlines()
    findings = [line for line in lines if _RUFF_FINDING_RE.match(line)]
    out = [f"ruff findings: {len(findings)}"]
    for f in findings[:10]:
        out.append(f"  {f}")
    if len(findings) > 10:
        out.append(f"  ... e mais {len(findings) - 10} omitidos")
    return out


def _summarize_generic(output: str, tail: int) -> list[str]:
    lines = output.splitlines()
    shown = lines[-tail:] if tail else lines
    out = [f"ultimas {len(shown)} de {len(lines)} linhas:"]
    out.extend(f"  {line}" for line in shown)
    return out


def _windows_executable_extensions() -> list[str]:
    raw = os.environ.get("PATHEXT") or _DEFAULT_WINDOWS_PATHEXT
    extensions: list[str] = []
    for value in raw.split(";"):
        extension = value.strip().casefold()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        if extension not in _WINDOWS_EXECUTABLE_EXTENSIONS:
            continue
        if extension not in extensions:
            extensions.append(extension)
    return extensions or [".com", ".exe", ".bat", ".cmd"]


def _resolve_program(program: str) -> str | None:
    if sys.platform != "win32":
        return shutil.which(program)

    suffix = Path(program).suffix.casefold()
    if suffix in _WINDOWS_EXECUTABLE_EXTENSIONS:
        return shutil.which(program)

    for extension in _windows_executable_extensions():
        resolved = shutil.which(f"{program}{extension}")
        if resolved:
            return resolved

    resolved = shutil.which(program)
    if resolved and Path(resolved).suffix.casefold() in _WINDOWS_EXECUTABLE_EXTENSIONS:
        return resolved
    return None


def _portable_command(cmd: list[str]) -> list[str]:
    if not cmd:
        return cmd
    resolved = _resolve_program(cmd[0])
    if not resolved:
        return cmd
    resolved_cmd = [resolved, *cmd[1:]]
    if sys.platform == "win32" and Path(resolved).suffix.casefold() in (
        _WINDOWS_BATCH_EXTENSIONS
    ):
        command_interpreter = (
            os.environ.get("COMSPEC") or shutil.which("cmd.exe") or "cmd.exe"
        )
        return [
            command_interpreter,
            "/d",
            "/c",
            resolved,
            *cmd[1:],
        ]
    return resolved_cmd


def _execute(cmd: list[str], timeout: int | None) -> tuple[int, str, float]:
    start = time.monotonic()
    portable_cmd = _portable_command(cmd)
    try:
        proc = subprocess.run(
            portable_cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        code = proc.returncode
    except FileNotFoundError as exc:
        output = f"[EXECUTABLE_NOT_FOUND] {cmd[0]}: {exc}\n"
        code = 127
    except OSError as exc:
        output = f"[EXECUTION_ERROR] {cmd[0]}: {exc}\n"
        code = 126
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "") + "\n[TIMEOUT]"
        code = 124
    duration = time.monotonic() - start
    return code, output, duration


def _strip_leading_separator(cmd: list[str]) -> list[str]:
    if cmd and cmd[0] == "--":
        return cmd[1:]
    return cmd


def run_block(
    block_id: str,
    cmd: list[str],
    front_key: str,
    timeout: int | None,
    full: bool,
    tail: int,
) -> dict:
    bdir = front_dir(front_key)
    (bdir / "logs").mkdir(parents=True, exist_ok=True)
    log_path = bdir / "logs" / f"{block_id}.log"

    code, output, duration = _execute(cmd, timeout)
    log_path.write_text(f"+ {' '.join(cmd)}\n\n{output}", encoding="utf-8")

    if full:
        summary_lines = output.splitlines()
    elif _looks_like_pytest(cmd):
        summary_lines = _summarize_pytest(output)
    elif _looks_like_ruff(cmd):
        summary_lines = _summarize_ruff(output)
    else:
        summary_lines = _summarize_generic(output, tail)

    result = {
        "id": block_id,
        "cmd": cmd,
        "exit_code": code,
        "duration_s": round(duration, 2),
        "log_path": str(log_path),
        "status": "PASS" if code == 0 else "FAIL",
        "summary": summary_lines,
    }
    return result


def cmd_run(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    validate_block_id(args.id)
    cmd = _strip_leading_separator(args.cmd)
    if not cmd:
        print("BLOCKED: nenhum comando fornecido apos '--'.")
        return 2

    if args.argfile:
        extra = [
            line.strip()
            for line in Path(args.argfile).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cmd = cmd + extra

    print(f"+ [{args.id}] {' '.join(cmd)}")
    result = run_block(args.id, cmd, front_key, args.timeout, args.full, args.tail)

    state = load_state(front_key)
    state.setdefault("blocks", {})[args.id] = {
        k: v for k, v in result.items() if k != "summary"
    }
    save_state(front_key, state)

    print_kv("exit_code", result["exit_code"])
    print_kv("duration_s", result["duration_s"])
    print_kv("log", result["log_path"])
    for line in result["summary"]:
        print(line)
    return result["exit_code"]


# ---------------------------------------------------------------------------
# run-parallel
# ---------------------------------------------------------------------------


def _needs_serial(cmd: list[str]) -> bool:
    joined = " ".join(cmd).lower()
    return "postgresql" in joined


def cmd_run_parallel(args: argparse.Namespace) -> int:
    front_key = _front_key(args)

    blocks: list[dict] = []
    if args.blocks_file:
        blocks = json.loads(Path(args.blocks_file).read_text(encoding="utf-8"))
    for raw in args.block or []:
        blocks.append(json.loads(raw))
    if not blocks:
        print("BLOCKED: nenhum bloco fornecido (--block ou --blocks-file).")
        return 2

    for b in blocks:
        validate_block_id(b["id"])
        auto_serial = _needs_serial(b["cmd"])
        b["_serial"] = bool(b.get("serial")) or auto_serial or args.serial
        b["_serial_reason"] = (
            "marcador postgresql detectado no comando"
            if auto_serial
            else (
                "--serial forcado"
                if args.serial
                else ("declarado no bloco" if b.get("serial") else None)
            )
        )

    serial_blocks = [b for b in blocks if b["_serial"]]
    parallel_blocks = [b for b in blocks if not b["_serial"]]

    results: list[dict] = []

    for b in serial_blocks:
        print(f"+ [serial:{b['id']}] {' '.join(b['cmd'])}  (motivo: {b['_serial_reason']})")
        results.append(run_block(b["id"], b["cmd"], front_key, args.timeout, False, 20))

    if parallel_blocks:
        jobs = args.jobs or max(1, min(len(parallel_blocks), 6))
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(
                    run_block, b["id"], b["cmd"], front_key, args.timeout, False, 20
                ): b
                for b in parallel_blocks
            }
            for fut in futures:
                results.append(fut.result())

    state = load_state(front_key)
    state.setdefault("blocks", {})
    for r in results:
        state["blocks"][r["id"]] = {k: v for k, v in r.items() if k != "summary"}
    save_state(front_key, state)

    print("\n=== resumo run-parallel ===")
    overall_pass = True
    for r in results:
        overall_pass = overall_pass and r["exit_code"] == 0
        print(
            f"- {r['id']}: {r['status']} "
            f"(exit={r['exit_code']}, {r['duration_s']}s, log={r['log_path']})"
        )
    for b in serial_blocks:
        print(f"  [serializado] {b['id']}: {b['_serial_reason']}")
    print_kv("veredito_agregado", "PASS" if overall_pass else "FAIL")
    return 0 if overall_pass else 1


# ---------------------------------------------------------------------------
# final
# ---------------------------------------------------------------------------


def cmd_final(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    branch = current_branch()
    state = load_state(front_key)
    preflight = state.get("preflight", {})

    head = current_head()
    tracked_dirty, untracked = status_porcelain()
    diff_stat = git("diff", "--stat").stdout.strip()
    final_dirty_fingerprint = _relevant_dirty_fingerprint()

    initial_branch = state.get("branch") or preflight.get("branch")
    initial_head = state.get("head_initial") or preflight.get("head")
    initial_dirty_fingerprint = preflight.get("dirty_fingerprint", [])
    dirty_changed_paths = _dirty_changed_paths(
        initial_dirty_fingerprint,
        final_dirty_fingerprint,
    )

    branch_changed = initial_branch is not None and branch != initial_branch
    head_changed = initial_head is not None and head != initial_head

    tracked_dirty_relevant = _relevant_paths(tracked_dirty)
    untracked_relevant = _relevant_paths(untracked)
    dirty_delta = bool(dirty_changed_paths)

    final_data = {
        "qa_contract_version": QA_CONTRACT_VERSION,
        "branch": branch,
        "head": head,
        "tracked_dirty": tracked_dirty,
        "tracked_dirty_relevant": tracked_dirty_relevant,
        "untracked": untracked,
        "untracked_relevant": untracked_relevant,
        "dirty_fingerprint_initial": initial_dirty_fingerprint,
        "dirty_fingerprint_final": final_dirty_fingerprint,
        "dirty_changed_paths": dirty_changed_paths,
        "dirty_delta": dirty_delta,
        "branch_changed": branch_changed,
        "head_changed": head_changed,
    }
    bdir = front_dir(front_key)
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "final.json").write_text(
        json.dumps(final_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    state["final"] = final_data
    save_state(front_key, state)

    print_kv("qa_contract_version", QA_CONTRACT_VERSION)
    print_kv("branch_final", branch)
    print_kv("head_final", head)
    print_kv("branch_changed_vs_test_start", branch_changed)
    print_kv("head_changed_vs_test_start", head_changed)
    print_kv("tracked_dirty_relevant_final", tracked_dirty_relevant or "none")
    print_kv("untracked_relevant_final", untracked_relevant or "none")
    print_kv("dirty_delta_vs_preflight", dirty_delta)
    print_kv("dirty_changed_paths", dirty_changed_paths or "none")
    print_kv("diff_stat", diff_stat or "(vazio)")

    if branch_changed or head_changed:
        print_kv(
            "repo_state",
            "ATENCAO: branch/HEAD mudou durante o QA; revisar antes do fechamento",
        )
        return 1

    if dirty_delta:
        print_kv(
            "repo_state",
            "AVISO: surgiram mudancas novas durante o QA; registrar no REPORT. "
            "Isso nao transforma PASS funcional em FAIL automaticamente.",
        )
    else:
        print_kv(
            "repo_state",
            "sem mudanca nova relevante produzida durante o QA",
        )
    return 0


# ---------------------------------------------------------------------------
# report-block
# ---------------------------------------------------------------------------


def cmd_report_block(args: argparse.Namespace) -> int:
    front_key = _front_key(args)
    state = load_state(front_key)
    if not state:
        print("BLOCKED: nenhum state.json encontrado para esta front_key.")
        return 1

    preflight = state.get("preflight", {})
    lines = []
    lines.append("# Relatório de QA")
    lines.append("")
    lines.append("## 1. Contexto")
    lines.append(f"- QA_ID: {state.get('qa_id', 'N/A')}")
    lines.append(f"- Front ID: {state.get('front_id', args.front_id)}")
    lines.append(
        f"- QA_CONTRACT_VERSION: {state.get('qa_contract_version', QA_CONTRACT_VERSION)}"
    )
    lines.append(f"- Branch: {state.get('branch', preflight.get('branch', 'N/A'))}")
    lines.append(
        f"- HEAD esperado no pacote: {preflight.get('expect_head') or 'N/A'}"
    )
    lines.append(
        f"- HEAD remoto observado: {preflight.get('remote_head') or 'N/A'}"
    )
    lines.append(
        f"- Commit efetivamente testado: "
        f"{state.get('head_initial', preflight.get('head', 'N/A'))}"
    )
    git_prep = []
    if preflight.get("did_switch"):
        git_prep.append(
            f"switch {preflight.get('switch_from') or '<detached>'} -> "
            f"{preflight.get('branch')}"
        )
    if preflight.get("did_ff"):
        git_prep.append(
            f"ff {preflight.get('pull_from')} -> {preflight.get('head')}"
        )
    lines.append(
        f"- Preparação Git realizada: {'; '.join(git_prep) if git_prep else 'NÃO'}"
    )
    initial_dirty = preflight.get("dirty_fingerprint", [])
    lines.append(
        f"- Working tree relevante inicial: {len(initial_dirty)} item(ns) dirty; "
        "não bloqueante por si só"
    )
    lines.append("")
    lines.append("## 2. Resumo")
    lines.append("| Caso | Status | Evidência principal |")
    lines.append("|---|---|---|")
    for block_id, b in state.get("blocks", {}).items():
        evidence = f"exit={b.get('exit_code')} log={b.get('log_path')}"
        lines.append(f"| {block_id} | {b.get('status', 'N/A')} | {evidence} |")
    final = state.get("final")
    if final:
        lines.append("")
        lines.append("## 7. Estado final do repositório (harness)")
        lines.append(f"- Branch final: {final.get('branch')}")
        lines.append(f"- HEAD final: {final.get('head')}")
        changed = final.get("dirty_changed_paths") or []
        if changed:
            lines.append(
                "- Aviso de mudanças novas durante o QA: " + ", ".join(changed)
            )
            lines.append(
                "- Efeito padrão: aviso; não converte PASS funcional em FAIL "
                "automaticamente."
            )
        else:
            lines.append("- Mudanças novas durante o QA: nenhuma")

    text = "\n".join(lines) + "\n"
    print(text)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _add_front_id(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--front-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=QA_CONTRACT_VERSION)
    sub = p.add_subparsers(dest="command", required=True)

    vp = sub.add_parser(
        "validate-package",
        help="Reject QA packages that depend operationally on Google Drive",
    )
    _add_front_id(vp)
    vp.add_argument("--qa-id", required=True)
    vp.add_argument("--package-file", required=True)
    vp.set_defaults(func=cmd_validate_package)

    pf = sub.add_parser(
        "preflight",
        help="Prepare the requested Git branch and record the effective QA target",
    )
    _add_front_id(pf)
    pf.add_argument("--expect-branch")
    pf.add_argument("--expect-head")
    pf.set_defaults(func=cmd_preflight)

    ws = sub.add_parser("workspace", help="Clean front workspace and seed REPORT.md")
    _add_front_id(ws)
    ws.add_argument("--qa-id", required=True)
    ws.add_argument("--no-clean", action="store_true")
    ws.set_defaults(func=cmd_workspace)

    dl = sub.add_parser("delta", help="List existing .py files changed between two refs")
    _add_front_id(dl)
    dl.add_argument("--from", dest="from_ref", required=True)
    dl.add_argument("--to", dest="to_ref", required=True)
    dl.add_argument("--print", dest="print_list", action="store_true")
    dl.set_defaults(func=cmd_delta)

    rn = sub.add_parser("run", help="Run one command and print compact summary")
    _add_front_id(rn)
    rn.add_argument("--id", required=True)
    rn.add_argument("--argfile")
    rn.add_argument("--timeout", type=int)
    rn.add_argument("--full", action="store_true")
    rn.add_argument("--tail", type=int, default=20)
    rn.add_argument("cmd", nargs=argparse.REMAINDER)
    rn.set_defaults(func=cmd_run)

    rp = sub.add_parser("run-parallel", help="Run independent blocks concurrently")
    _add_front_id(rp)
    rp.add_argument("--block", action="append", help='JSON: {"id":..,"cmd":[..]}')
    rp.add_argument("--blocks-file")
    rp.add_argument("--jobs", type=int)
    rp.add_argument("--serial", action="store_true")
    rp.add_argument("--timeout", type=int)
    rp.set_defaults(func=cmd_run_parallel)

    fn = sub.add_parser("final", help="Re-check Git state against preflight")
    _add_front_id(fn)
    fn.set_defaults(func=cmd_final)

    rb = sub.add_parser("report-block", help="Emit ready-to-paste Markdown")
    _add_front_id(rb)
    rb.set_defaults(func=cmd_report_block)

    return p


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy codepage; force UTF-8 so accented
    # PT-BR strings in REPORT.md-flavored output don't come out as mojibake.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
