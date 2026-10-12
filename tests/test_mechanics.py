import json
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


def run(cwd, *args):
    return subprocess.run([sys.executable, str(HAR), *args], cwd=cwd, text=True, capture_output=True)


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def init_repo(tmp):
    p = Path(tmp) / 'p'
    p.mkdir()
    git(p, 'init', '-b', 'main')
    git(p, 'config', 'user.email', 'qa@example.test')
    git(p, 'config', 'user.name', 'QA')
    (p / 'a.txt').write_text('a')
    git(p, 'add', '.')
    git(p, 'commit', '-m', 'init')
    return p


def package(p, head, qa='QA-H3-demo-001'):
    f = p.parent / 'package.txt'
    sections = ''.join(f'\n[{name}]\nx\n' for name in SECTIONS)
    f.write_text(
        'QA_CONTRACT_VERSION: H3.0.0\n'
        f'QA_ID: {qa}\n'
        'QA_PURPOSE: FORMAL\n'
        'front_id: demo\n'
        f'HARNESS_REF: {HARNESS_SHA}\n'
        f'CREATED_AT: {CREATED_AT}\n'
        'REVISION_POLICY: EXACT\n'
        'EXPECT_BRANCH: main\n'
        f'EXPECT_HEAD: {head}\n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n'
        + sections
    )
    return f


def args(p, f):
    return [
        '--product-worktree', str(p), '--front-id', 'demo',
        '--qa-id', 'QA-H3-demo-001', '--harness-ref', HARNESS_SHA, '--package-file', str(f),
    ]


def test_exact_end_to_end_records_mechanical_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(p, git(p, 'rev-parse', 'HEAD'))
        a = args(p, f)
        assert run(p, 'validate-package', *a).returncode == 0
        assert run(p, 'preflight', *a).returncode == 0
        assert run(p, 'workspace', *a).returncode == 0
        result_dir = p / '.tmp/qa/run/result'
        assert not (result_dir / 'REPORT.md').exists()
        command = run(p, 'run', *a, '--id', 'ok', '--', sys.executable, '-c', 'print(123)')
        assert command.returncode == 0
        final = run(p, 'finalize', '--product-worktree', str(p), '--front-id', 'demo', '--qa-id', 'QA-H3-demo-001', '--harness-ref', HARNESS_SHA, '--package-file', str(f))
        assert final.returncode == 0
        evidence = json.loads((result_dir / 'EVIDENCE.json').read_text())
        assert evidence['commands'][0]['id'] == 'ok'
        assert evidence['findings'] == []


def test_exact_mismatch_and_dirty_are_operator_actions():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(p, '0' * 40)
        a = args(p, f)
        assert run(p, 'validate-package', *a).returncode == 0
        mismatch = run(p, 'preflight', *a)
        assert mismatch.returncode == 3 and 'OPERATOR_ACTION_REQUIRED' in mismatch.stdout
        f = package(p, git(p, 'rev-parse', 'HEAD'))
        a = args(p, f)
        assert run(p, 'validate-package', *a).returncode == 0
        (p / 'a.txt').write_text('dirty')
        dirty = run(p, 'preflight', *a)
        assert dirty.returncode == 3 and 'OPERATOR_ACTION_REQUIRED' in dirty.stdout


def test_package_mutation_after_validation_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(p, git(p, 'rev-parse', 'HEAD'))
        a = args(p, f)
        assert run(p, 'validate-package', *a).returncode == 0
        f.write_text(f.read_text() + '# mutate\n')
        result = run(p, 'preflight', *a)
        assert result.returncode != 0
        assert 'changed after validation' in result.stderr


def test_finalize_detects_checkout_change():
    with tempfile.TemporaryDirectory() as tmp:
        p = init_repo(tmp)
        f = package(p, git(p, 'rev-parse', 'HEAD'))
        a = args(p, f)
        run(p, 'validate-package', *a)
        run(p, 'preflight', *a)
        run(p, 'workspace', *a)
        (p / 'new.txt').write_text('changed during qa')
        final = run(p, 'finalize', '--product-worktree', str(p), '--front-id', 'demo', '--qa-id', 'QA-H3-demo-001', '--harness-ref', HARNESS_SHA, '--package-file', str(f))
        assert final.returncode == 1
        assert 'working tree changed during QA' in json.loads(final.stdout)['findings']
