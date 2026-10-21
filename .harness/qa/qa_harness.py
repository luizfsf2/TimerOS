#!/usr/bin/env python3
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
from datetime import datetime
from pathlib import Path

QA_CONTRACT_VERSION = "H3.0.0"
RESULT_DESTINATION = ".tmp/qa/run/result/"
SAFE_SEG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DRIVE_RE = re.compile(r"(?i)https?://(?:drive|docs)\.google\.com|\b(?:GOOGLE_)?DRIVE(?:_(?:FILE|FOLDER))?_?ID\s*:")
REQUIRED_SECTIONS = [
    "OBJECTIVE",
    "CONTEXT",
    "DECISIONS",
    "DELTA",
    "RISKS",
    "EXPECTED_BEHAVIOR",
    "TESTS_ALREADY_RUN",
    "SCOPE",
    "LIMITS",
    "RETURN_CONTRACT",
]
WINDOWS_BATCH = {".cmd", ".bat"}
WINDOWS_NATIVE = {".exe", ".com"}


def die(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def validate_seg(value: str, label: str) -> str:
    if value in {".", ".."} or not SAFE_SEG.fullmatch(value):
        raise ValueError(f"{label} must be a safe single path segment")
    return value


def validate_qa_id(front_id: str, qa_id: str) -> None:
    if not re.fullmatch(rf"QA-H3-{re.escape(front_id)}-(\d{{3,}})", qa_id):
        raise ValueError(f"QA_ID must match QA-H3-{front_id}-<NNN>")


def package_values(text: str, field: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(rf"(?m)^[ \t]*{re.escape(field)}[ \t]*:[ \t]*(.*?)[ \t]*$", text)
    ]


def package_single(text: str, field: str, issues: list[str]) -> str | None:
    values = package_values(text, field)
    if not values:
        issues.append(f"missing required field: {field}")
        return None
    if len(values) != 1:
        issues.append(f"field must appear exactly once: {field}")
        return None
    return values[0]


def valid_created_at(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_package_text(text: str, front_id: str, qa_id: str, harness_ref: str) -> list[str]:
    validate_seg(front_id, "front_id")
    validate_qa_id(front_id, qa_id)
    issues: list[str] = []

    version = package_single(text, "QA_CONTRACT_VERSION", issues)
    package_qa_id = package_single(text, "QA_ID", issues)
    package_front = package_single(text, "front_id", issues)
    package_harness_ref = package_single(text, "HARNESS_REF", issues)
    created_at = package_single(text, "CREATED_AT", issues)
    purpose = package_single(text, "QA_PURPOSE", issues)
    policy = package_single(text, "REVISION_POLICY", issues)
    expect_branch = package_single(text, "EXPECT_BRANCH", issues)
    expect_head = package_single(text, "EXPECT_HEAD", issues)
    destination = package_single(text, "RESULT_DESTINATION", issues)

    if version and version != QA_CONTRACT_VERSION:
        issues.append(f"QA_CONTRACT_VERSION must be {QA_CONTRACT_VERSION}")
    if package_qa_id and package_qa_id != qa_id:
        issues.append(f"QA_ID must be exactly {qa_id}")
    if package_front and package_front != front_id:
        issues.append(f"front_id must be exactly {front_id}")
    if package_harness_ref and not re.fullmatch(r"[0-9a-fA-F]{40}", package_harness_ref):
        issues.append("HARNESS_REF must be an exact 40-hex SHA")
    if package_harness_ref and package_harness_ref.lower() != harness_ref.lower():
        issues.append(f"HARNESS_REF must match launcher harness ref {harness_ref.lower()}")
    if created_at and not valid_created_at(created_at):
        issues.append("CREATED_AT must be ISO 8601 with timezone")
    if purpose and purpose not in {"CHECKPOINT", "FORMAL"}:
        issues.append("QA_PURPOSE must be CHECKPOINT or FORMAL")
    if policy and policy not in {"EXACT", "BRANCH_CURRENT"}:
        issues.append("REVISION_POLICY must be EXACT or BRANCH_CURRENT")
    if policy == "EXACT" and expect_head == "":
        issues.append("EXPECT_HEAD is required for EXACT")
    if policy == "BRANCH_CURRENT" and expect_branch == "":
        issues.append("EXPECT_BRANCH is required for BRANCH_CURRENT")

    if destination and destination.replace("\\", "/") != RESULT_DESTINATION:
        issues.append(f"RESULT_DESTINATION must be exactly {RESULT_DESTINATION}")

    for section in REQUIRED_SECTIONS:
        if not re.search(rf"(?m)^\[{re.escape(section)}\]\s*$", text):
            issues.append(f"missing required section: [{section}]")

    if DRIVE_RE.search(text):
        issues.append("Google Drive URL/ID is forbidden inside executable QA package")

    return issues


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def current_branch(cwd: Path) -> str:
    result = git(cwd, "branch", "--show-current")
    return result.stdout.strip() or "DETACHED"


def current_head(cwd: Path) -> str:
    result = git(cwd, "rev-parse", "HEAD")
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "cannot resolve HEAD")
    return result.stdout.strip()


def dirty_fingerprint(cwd: Path) -> list[dict[str, str | None]]:
    result = git(cwd, "status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "cannot inspect working tree")

    output: list[dict[str, str | None]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        rel = line[3:].strip().split(" -> ")[-1].replace("\\", "/")
        if rel.startswith(".tmp/qa/"):
            continue
        absolute = cwd / rel
        digest: str | None = None
        if absolute.is_symlink():
            digest = "symlink:" + os.readlink(absolute)
        elif absolute.is_file():
            try:
                digest = hashlib.sha256(absolute.read_bytes()).hexdigest()
            except OSError:
                digest = "<unreadable>"
        output.append({"status": line[:2], "path": rel, "sha256": digest})

    return sorted(output, key=lambda item: (item["path"] or "", item["status"] or "", item["sha256"] or ""))


def qa_root(product: Path) -> Path:
    return product / ".tmp" / "qa" / "run"


def result_root(product: Path) -> Path:
    return qa_root(product) / "result"


def state_file(product: Path, front_id: str, qa_id: str) -> Path:
    return qa_root(product) / "state.json"


def load_state(product: Path, front_id: str, qa_id: str) -> dict:
    path = state_file(product, front_id, qa_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text("utf-8"))


def save_state(product: Path, front_id: str, qa_id: str, state: dict) -> None:
    path = state_file(product, front_id, qa_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", "utf-8")


def reset_result(product: Path) -> Path:
    result = result_root(product)
    if result.exists():
        shutil.rmtree(result)
    (result / "logs").mkdir(parents=True, exist_ok=True)
    (result / "screenshots").mkdir(parents=True, exist_ok=True)
    return result


def ensure_harness_identity(state: dict, harness_ref: str) -> None:
    if state.get("harness_ref") != harness_ref.lower():
        raise ValueError("launcher harness ref changed after package validation")


def ensure_package_unchanged(state: dict, package: Path) -> None:
    expected = state.get("package_sha256")
    if not expected:
        raise ValueError("package validation state missing; run validate-package")
    if sha256_file(package) != expected:
        raise ValueError("package changed after validation; re-run validate-package")


def package_field(package: Path, field: str) -> str:
    values = package_values(package.read_text("utf-8-sig"), field)
    return values[0] if values else ""


def cmd_validate(args) -> int:
    product = Path(args.product_worktree).resolve()
    package = Path(args.package_file).resolve()
    try:
        text = package.read_text("utf-8-sig")
        issues = validate_package_text(text, args.front_id, args.qa_id, args.harness_ref)
    except Exception as exc:
        return die(str(exc))

    if issues:
        for issue in issues:
            print("INVALID:", issue)
        state_path = state_file(product, args.front_id, args.qa_id)
        if state_path.exists():
            state_path.unlink()
        return 2

    state = {
        "contract_version": QA_CONTRACT_VERSION,
        "front_id": args.front_id,
        "qa_id": args.qa_id,
        "harness_ref": args.harness_ref.lower(),
        "created_at": package_single(text, "CREATED_AT", []),
        "package_file": str(package),
        "package_sha256": sha256_file(package),
        "package_validated": True,
        "package_validated_at": time.time(),
        "commands": [],
    }
    save_state(product, args.front_id, args.qa_id, state)
    print("VALID")
    return 0


def operator_action(state: dict, product: Path, args, reason: str) -> int:
    state["preflight"] = "OPERATOR_ACTION_REQUIRED"
    state["operator_action_reason"] = reason
    save_state(product, args.front_id, args.qa_id, state)
    print(f"OPERATOR_ACTION_REQUIRED: {reason}")
    return 3


def cmd_preflight(args) -> int:
    product = Path(args.product_worktree).resolve()
    package = Path(args.package_file).resolve()
    reset_result(product)
    state = load_state(product, args.front_id, args.qa_id)
    if not state.get("package_validated"):
        return die("package must be validated before preflight")

    state["commands"] = []
    state["workspace_created"] = False
    save_state(product, args.front_id, args.qa_id, state)

    try:
        ensure_harness_identity(state, args.harness_ref)
        ensure_package_unchanged(state, package)
        policy = package_field(package, "REVISION_POLICY")
        expect_branch = package_field(package, "EXPECT_BRANCH")
        expect_head = package_field(package, "EXPECT_HEAD")
        branch = current_branch(product)
        head = current_head(product)
        dirty = dirty_fingerprint(product)
    except Exception as exc:
        return die(str(exc))

    state.update(
        {
            "revision_policy": policy,
            "expect_branch": expect_branch,
            "expect_head": expect_head,
            "observed_branch": branch,
            "observed_head": head,
            "dirty_baseline": dirty,
        }
    )

    if policy == "EXACT":
        if expect_branch and branch != expect_branch:
            return operator_action(state, product, args, "branch mismatch")
        if head != expect_head:
            return operator_action(state, product, args, "HEAD mismatch")
        if dirty:
            return operator_action(state, product, args, "relevant dirty state")
    elif policy == "BRANCH_CURRENT":
        if branch != expect_branch:
            return operator_action(state, product, args, "branch mismatch")
    else:
        return die("unsupported REVISION_POLICY")

    state["preflight"] = "PROCEED"
    state.pop("operator_action_reason", None)
    save_state(product, args.front_id, args.qa_id, state)
    print(f"PROCEED branch={branch} head={head}")
    return 0


def cmd_workspace(args) -> int:
    product = Path(args.product_worktree).resolve()
    package = Path(args.package_file).resolve()
    state = load_state(product, args.front_id, args.qa_id)
    if state.get("preflight") != "PROCEED":
        return die("preflight must be PROCEED before workspace")

    try:
        ensure_harness_identity(state, args.harness_ref)
        ensure_package_unchanged(state, package)
    except Exception as exc:
        return die(str(exc))

    root = qa_root(product)
    for path in [
        root / "artifacts",
        result_root(product) / "screenshots",
        result_root(product) / "logs",
    ]:
        path.mkdir(parents=True, exist_ok=True)

    state["workspace_created"] = True
    save_state(product, args.front_id, args.qa_id, state)
    print(root / "result")
    return 0


def windows_exts() -> list[str]:
    raw = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    return [item.lower() for item in raw.split(";") if item]


def resolve_program(program: str) -> str | None:
    if os.name != "nt":
        return shutil.which(program)
    suffix = os.path.splitext(program)[1].lower()
    if suffix in WINDOWS_NATIVE | WINDOWS_BATCH:
        return shutil.which(program)
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        for extension in windows_exts():
            for candidate_extension in {extension.lower(), extension.upper()}:
                candidate = os.path.join(directory, program + candidate_extension)
                if os.path.isfile(candidate):
                    return candidate
    return shutil.which(program)


def portable_command(command: list[str]) -> list[str]:
    if not command:
        return command
    resolved = resolve_program(command[0])
    if not resolved:
        return command
    if os.name == "nt" and os.path.splitext(resolved)[1].lower() in WINDOWS_BATCH:
        comspec = os.environ.get("COMSPEC") or shutil.which("cmd.exe") or "cmd.exe"
        return [comspec, "/d", "/c", resolved, *command[1:]]
    return [resolved, *command[1:]]


def execute(command: list[str], cwd: Path, timeout: int | None) -> tuple[int, str, float]:
    started = time.monotonic()
    portable = portable_command(command)
    try:
        result = subprocess.run(
            portable,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=False,
        )
        return result.returncode, result.stdout, time.monotonic() - started
    except FileNotFoundError as exc:
        return 127, str(exc), time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        return 124, output + "\nTIMEOUT", time.monotonic() - started
    except OSError as exc:
        return 126, str(exc), time.monotonic() - started


def assert_runnable(args) -> tuple[Path, dict, Path]:
    product = Path(args.product_worktree).resolve()
    package = Path(args.package_file).resolve()
    state = load_state(product, args.front_id, args.qa_id)
    if not state.get("workspace_created"):
        raise ValueError("workspace must be created first")
    ensure_harness_identity(state, args.harness_ref)
    ensure_package_unchanged(state, package)
    return product, state, package


def cmd_run(args) -> int:
    try:
        product, state, _ = assert_runnable(args)
        validate_seg(args.id, "command id")
    except Exception as exc:
        return die(str(exc))

    log_path = result_root(product) / "logs" / f"{args.id}.log"
    returncode, output, duration = execute(args.command, product, args.timeout)
    log_path.write_text(output, "utf-8", errors="replace")

    record = {
        "id": args.id,
        "command": args.command,
        "returncode": returncode,
        "duration": duration,
        "log": str(log_path),
    }
    state.setdefault("commands", []).append(record)
    save_state(product, args.front_id, args.qa_id, state)
    print(json.dumps(record))
    return returncode


def cmd_finalize(args) -> int:
    product = Path(args.product_worktree).resolve()
    state = load_state(product, args.front_id, args.qa_id)
    if not state.get("workspace_created"):
        return die("workspace must be created first")

    try:
        ensure_harness_identity(state, args.harness_ref)
        ensure_package_unchanged(state, Path(args.package_file).resolve())
        final_branch = current_branch(product)
        final_head = current_head(product)
        final_dirty = dirty_fingerprint(product)
    except Exception as exc:
        return die(str(exc))

    findings: list[str] = []
    if final_branch != state.get("observed_branch"):
        findings.append("branch changed during QA")
    if final_head != state.get("observed_head"):
        findings.append("HEAD changed during QA")
    if final_dirty != state.get("dirty_baseline"):
        findings.append("working tree changed during QA")

    evidence = {
        "qa_id": args.qa_id,
        "front_id": args.front_id,
        "harness_ref": state.get("harness_ref"),
        "created_at": state.get("created_at"),
        "revision_policy": state.get("revision_policy"),
        "expected_branch": state.get("expect_branch"),
        "expected_head": state.get("expect_head"),
        "observed_branch": state.get("observed_branch"),
        "observed_head": state.get("observed_head"),
        "dirty_baseline": state.get("dirty_baseline"),
        "commands": state.get("commands", []),
        "final_branch": final_branch,
        "final_head": final_head,
        "final_dirty": final_dirty,
        "findings": findings,
    }

    result_dir = result_root(product)
    result_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = result_dir / "EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps({"evidence": str(evidence_path), "findings": findings}))
    return 1 if findings else 0


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product-worktree", required=True)
    parser.add_argument("--front-id", required=True)
    parser.add_argument("--qa-id", required=True)
    parser.add_argument("--harness-ref", required=True)
    parser.add_argument("--package-file", required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    root.add_argument("--version", action="version", version=QA_CONTRACT_VERSION)
    sub = root.add_subparsers(dest="cmd", required=True)

    command = sub.add_parser("validate-package")
    common(command)
    command.set_defaults(func=cmd_validate)

    command = sub.add_parser("preflight")
    common(command)
    command.set_defaults(func=cmd_preflight)

    command = sub.add_parser("workspace")
    common(command)
    command.set_defaults(func=cmd_workspace)

    command = sub.add_parser("run")
    common(command)
    command.add_argument("--id", required=True)
    command.add_argument("--timeout", type=int)
    command.add_argument("command", nargs=argparse.REMAINDER)
    command.set_defaults(func=cmd_run)

    command = sub.add_parser("finalize")
    common(command)
    command.set_defaults(func=cmd_finalize)

    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if getattr(args, "command", None) and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    try:
        return args.func(args)
    except ValueError as exc:
        return die(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
