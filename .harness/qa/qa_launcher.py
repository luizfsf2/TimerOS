#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

QA_LAUNCHER_VERSION = "H3-QA-LAUNCHER-2"
HARNESS_LAUNCHER_PATH = "tools/qa_launcher.py"
HARNESS_PROMPT_PATH = "prompts/QA_AGENT_MAIN_PROMPT.md"
HARNESS_HELPER_PATH = "tools/qa_harness.py"
RUN_REL = Path(".tmp") / "qa" / "run"
RESULT_DESTINATION = ".tmp/qa/run/result/"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SAFE_SEG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def die(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def safe_seg(value: str, label: str) -> str:
    if value in {".", ".."} or not SAFE_SEG.fullmatch(value):
        raise ValueError(f"{label} must be a safe single path segment")
    return value


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_text(repo: Path, *args: str) -> str:
    result = git(repo, *args)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "git command failed")
    return result.stdout.decode("utf-8", errors="replace").strip()


def git_bytes(repo: Path, *args: str) -> bytes:
    result = git(repo, *args)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "git command failed")
    return result.stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_value(text: str, field: str) -> str:
    values = [
        match.group(1).strip()
        for match in re.finditer(
            rf"(?m)^[ \t]*{re.escape(field)}[ \t]*:[ \t]*(.*?)[ \t]*$",
            text,
        )
    ]
    if len(values) != 1:
        raise ValueError(f"package must contain exactly one {field}")
    return values[0]


def validate_created_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("CREATED_AT must be ISO 8601 with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("CREATED_AT must be ISO 8601 with timezone")
    return value


def package_identity_bytes(data: bytes) -> tuple[str, str, str, str]:
    text = data.decode("utf-8-sig")
    harness_ref = package_value(text, "HARNESS_REF").lower()
    front_id = package_value(text, "front_id")
    qa_id = package_value(text, "QA_ID")
    created_at = validate_created_at(package_value(text, "CREATED_AT"))
    destination = package_value(text, "RESULT_DESTINATION").replace("\\", "/")
    if destination != RESULT_DESTINATION:
        raise ValueError(f"RESULT_DESTINATION must be exactly {RESULT_DESTINATION}")
    if not SHA_RE.fullmatch(harness_ref):
        raise ValueError("HARNESS_REF must be an exact 40-hex SHA")
    safe_seg(front_id, "front_id")
    safe_seg(qa_id, "qa_id")
    return harness_ref, front_id, qa_id, created_at


def verify_harness_commit(repo: Path, harness_ref: str) -> None:
    if not repo.is_dir():
        raise ValueError("harness repository path does not exist")
    resolved = git_text(repo, "rev-parse", "--verify", f"{harness_ref}^{{commit}}").lower()
    if resolved != harness_ref:
        raise ValueError("Harness ref did not resolve to the requested exact commit")


def pinned_blob(repo: Path, harness_ref: str, path: str) -> bytes:
    try:
        return git_bytes(repo, "show", f"{harness_ref}:{path}")
    except ValueError as exc:
        raise ValueError(
            f"pinned QA asset missing at Harness ref: {path}; legacy product fallback is forbidden"
        ) from exc


def product_identity(product: Path) -> tuple[str, str]:
    if not product.is_dir():
        raise ValueError("product worktree path does not exist")
    branch = git_text(product, "branch", "--show-current") or "DETACHED"
    head = git_text(product, "rev-parse", "HEAD")
    return branch, head


def reset_session(product: Path) -> Path:
    root = product / RUN_REL
    if root.exists():
        shutil.rmtree(root)
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def prepare_session(
    harness_repository: str | Path,
    package_file: str | Path,
    product_worktree: str | Path,
) -> dict:
    source_package = Path(package_file).resolve()
    package_bytes = source_package.read_bytes()
    harness_ref, front_id, qa_id, created_at = package_identity_bytes(package_bytes)

    repo = Path(harness_repository).resolve()
    product = Path(product_worktree).resolve()
    verify_harness_commit(repo, harness_ref)
    branch, head = product_identity(product)

    launcher = pinned_blob(repo, harness_ref, HARNESS_LAUNCHER_PATH)
    prompt = pinned_blob(repo, harness_ref, HARNESS_PROMPT_PATH)
    helper = pinned_blob(repo, harness_ref, HARNESS_HELPER_PATH)

    root = reset_session(product)
    bootstrap = root / "bootstrap" / harness_ref
    bootstrap.mkdir(parents=True, exist_ok=True)

    package_path = root / "PACOTE_QA.txt"
    manifest_path = root / "LAUNCH.json"
    launcher_path = bootstrap / "qa_launcher.py"
    prompt_path = bootstrap / "QA_AGENT_MAIN_PROMPT.md"
    helper_path = bootstrap / "qa_harness.py"

    package_path.write_bytes(package_bytes)
    launcher_path.write_bytes(launcher)
    prompt_path.write_bytes(prompt)
    helper_path.write_bytes(helper)
    for executable in [launcher_path, helper_path]:
        try:
            executable.chmod(0o755)
        except OSError:
            pass

    manifest = {
        "launcher_version": QA_LAUNCHER_VERSION,
        "harness_ref": harness_ref,
        "harness_repository": str(repo),
        "created_at": created_at,
        "qa_launcher_source": HARNESS_LAUNCHER_PATH,
        "qa_launcher": str(launcher_path),
        "qa_launcher_sha256": sha256(launcher),
        "qa_prompt_source": HARNESS_PROMPT_PATH,
        "qa_prompt": str(prompt_path),
        "qa_prompt_sha256": sha256(prompt),
        "qa_helper_source": HARNESS_HELPER_PATH,
        "qa_helper": str(helper_path),
        "qa_helper_sha256": sha256(helper),
        "package_file": str(package_path),
        "package_sha256": sha256(package_bytes),
        "product_worktree": str(product),
        "product_branch": branch,
        "product_head": head,
        "front_id": front_id,
        "qa_id": qa_id,
        "run_root": str(root),
        "artifacts_root": str(root / "artifacts"),
        "result_root": str(root / "result"),
        "result_destination": RESULT_DESTINATION,
        "legacy_product_helpers_allowed": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", "utf-8")
    manifest["manifest"] = str(manifest_path)
    return manifest


def load_manifest(path: str | Path) -> dict:
    manifest_path = Path(path).resolve()
    data = json.loads(manifest_path.read_text("utf-8"))
    required = {
        "harness_ref", "created_at", "qa_launcher", "qa_launcher_sha256",
        "qa_prompt", "qa_prompt_sha256", "qa_helper", "qa_helper_sha256",
        "package_file", "package_sha256", "product_worktree", "front_id",
        "qa_id", "run_root", "artifacts_root", "result_root", "result_destination",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError("launcher manifest missing fields: " + ", ".join(missing))
    if data.get("legacy_product_helpers_allowed") is not False:
        raise ValueError("launcher manifest does not forbid legacy product helpers")
    if data.get("result_destination") != RESULT_DESTINATION:
        raise ValueError("launcher manifest has invalid result destination")

    checks = [
        ("QA launcher", Path(data["qa_launcher"]).resolve(), data["qa_launcher_sha256"]),
        ("QA prompt", Path(data["qa_prompt"]).resolve(), data["qa_prompt_sha256"]),
        ("QA helper", Path(data["qa_helper"]).resolve(), data["qa_helper_sha256"]),
        ("QA package", Path(data["package_file"]).resolve(), data["package_sha256"]),
    ]
    for label, path_obj, expected in checks:
        if sha256(path_obj.read_bytes()) != expected:
            raise ValueError(f"{label} changed after bootstrap")
    return data


def cmd_prepare(args) -> int:
    try:
        manifest = prepare_session(
            args.harness_repository,
            args.package_file,
            args.product_worktree,
        )
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        return die(str(exc))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cmd_helper(args) -> int:
    try:
        manifest = load_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return die(str(exc))

    helper_args = list(args.helper_args)
    if helper_args and helper_args[0] == "--":
        helper_args = helper_args[1:]
    if not helper_args:
        return die("helper subcommand is required")

    subcommand, *rest = helper_args
    command = [
        sys.executable,
        manifest["qa_helper"],
        subcommand,
        "--product-worktree",
        manifest["product_worktree"],
        "--front-id",
        manifest["front_id"],
        "--qa-id",
        manifest["qa_id"],
        "--harness-ref",
        manifest["harness_ref"],
        "--package-file",
        manifest["package_file"],
        *rest,
    ]
    return subprocess.run(command, check=False).returncode


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Pin-safe QA bootstrap for Harness V3 with a single ephemeral .tmp/qa/run workspace."
    )
    root.add_argument("--version", action="version", version=QA_LAUNCHER_VERSION)
    sub = root.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--harness-repository", required=True)
    prepare.add_argument("--package-file", required=True)
    prepare.add_argument("--product-worktree", required=True)
    prepare.set_defaults(func=cmd_prepare)

    helper = sub.add_parser("helper")
    helper.add_argument("--manifest", required=True)
    helper.add_argument("helper_args", nargs=argparse.REMAINDER)
    helper.set_defaults(func=cmd_helper)

    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
