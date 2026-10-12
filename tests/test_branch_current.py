import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAR = ROOT / 'tools/qa_harness.py'
HARNESS_SHA = 'a' * 40
CREATED_AT = '2026-10-09T17:30:00-03:00'

SECTIONS = [
    'OBJECTIVE', 'CONTEXT', 'DECISIONS', 'DELTA', 'RISKS',
    'EXPECTED_BEHAVIOR', 'TESTS_ALREADY_RUN', 'SCOPE', 'LIMITS',
    'RETURN_CONTRACT',
]


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def run(cwd, *args):
    return subprocess.run([sys.executable, str(HAR), *args], cwd=cwd, text=True, capture_output=True)


def init_repo(tmp):
    p = Path(tmp) / 'p'
    p.mkdir()
    sh(p, 'git', 'init', '-b', 'main')
    sh(p, 'git', 'config', 'user.email', 'qa@example.test')
    sh(p, 'git', 'config', 'user.name', 'QA')
    (p / 'a').write_text('1')
    sh(p, 'git', 'add', '.')
    sh(p, 'git', 'commit', '-m', 'init')
    return p


def package(base, p, expect_head=None):
    qa = 'QA-H3-demo-001'
    f = Path(base) / 'package.txt'
    sections = ''.join(f'\n[{name}]\nx\n' for name in SECTIONS)
    f.write_text(
        'QA_CONTRACT_VERSION: H3.0.0\n'
        f'QA_ID: {qa}\n'
        'QA_PURPOSE: FORMAL\n'
        'front_id: demo\n'
        f'HARNESS_REF: {HARNESS_SHA}\n'
        f'CREATED_AT: {CREATED_AT}\n'
        'REVISION_POLICY: BRANCH_CURRENT\n'
        'EXPECT_BRANCH: main\n'
        f'EXPECT_HEAD: {expect_head if expect_head is not None else sh(p, "git", "rev-parse", "HEAD")}\n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n'
        + sections
    )
    return f


def prep(p, f):
    args = [
        '--product-worktree', str(p), '--front-id', 'demo',
        '--qa-id', 'QA-H3-demo-001', '--harness-ref', HARNESS_SHA, '--package-file', str(f),
    ]
    assert run(p, 'validate-package', *args).returncode == 0
    return args


def test_branch_current_uses_observed_head_not_emission_head():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(tmp, p, expect_head='0' * 40)
        args = prep(p, f)
        result = run(p, 'preflight', *args)
        assert result.returncode == 0
        assert sh(p, 'git', 'rev-parse', 'HEAD') in result.stdout


def test_branch_mismatch_resumes_same_qa_id_after_operator_action():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(tmp, p)
        sh(p, 'git', 'switch', '-c', 'other')
        args = prep(p, f)
        blocked = run(p, 'preflight', *args)
        assert blocked.returncode == 3
        assert 'OPERATOR_ACTION_REQUIRED' in blocked.stdout
        sh(p, 'git', 'switch', 'main')
        resumed = run(p, 'preflight', *args)
        assert resumed.returncode == 0
        assert 'PROCEED' in resumed.stdout
