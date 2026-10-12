import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qh', ROOT / 'tools/qa_harness.py')
qh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qh)

HARNESS_SHA = 'a' * 40
CREATED_AT = '2026-10-09T17:30:00-03:00'

SECTIONS = [
    'OBJECTIVE', 'CONTEXT', 'DECISIONS', 'DELTA', 'RISKS',
    'EXPECTED_BEHAVIOR', 'TESTS_ALREADY_RUN', 'SCOPE', 'LIMITS',
    'RETURN_CONTRACT',
]


def pkg(front='demo', qa='QA-H3-demo-001', purpose='FORMAL', policy='EXACT', branch='main', head='abc'):
    sections = ''.join(f'\n[{name}]\nx\n' for name in SECTIONS)
    return (
        f'QA_CONTRACT_VERSION: H3.0.0\n'
        f'QA_ID: {qa}\n'
        f'QA_PURPOSE: {purpose}\n'
        f'front_id: {front}\n'
        f'HARNESS_REF: {HARNESS_SHA}\n'
        f'CREATED_AT: {CREATED_AT}\n'
        f'REVISION_POLICY: {policy}\n'
        f'EXPECT_BRANCH: {branch}\n'
        f'EXPECT_HEAD: {head}\n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n'
        + sections
    )


def test_valid_package():
    assert qh.validate_package_text(pkg(), 'demo', 'QA-H3-demo-001', HARNESS_SHA) == []


def test_checkpoint_is_valid():
    assert qh.validate_package_text(pkg(purpose='CHECKPOINT'), 'demo', 'QA-H3-demo-001', HARNESS_SHA) == []


def test_bad_version():
    issues = qh.validate_package_text(pkg().replace('H3.0.0', 'H2.5.3', 1), 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('QA_CONTRACT_VERSION' in issue for issue in issues)


def test_bad_id():
    try:
        qh.validate_package_text(pkg(), 'demo', 'QA-demo-001', HARNESS_SHA)
        assert False
    except ValueError:
        pass


def test_bad_purpose():
    issues = qh.validate_package_text(pkg().replace('QA_PURPOSE: FORMAL', 'QA_PURPOSE: X'), 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('QA_PURPOSE' in issue for issue in issues)


def test_bad_policy():
    issues = qh.validate_package_text(pkg().replace('REVISION_POLICY: EXACT', 'REVISION_POLICY: X'), 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('REVISION_POLICY' in issue for issue in issues)


def test_exact_requires_head():
    issues = qh.validate_package_text(pkg(head=''), 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('EXPECT_HEAD' in issue for issue in issues)


def test_branch_current_requires_branch():
    issues = qh.validate_package_text(pkg(policy='BRANCH_CURRENT', branch='', head=''), 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('EXPECT_BRANCH' in issue for issue in issues)


def test_missing_context_section_fails():
    text = pkg().replace('\n[CONTEXT]\nx\n', '\n', 1)
    issues = qh.validate_package_text(text, 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('[CONTEXT]' in issue for issue in issues)


def test_drive_url_rejected():
    issues = qh.validate_package_text(pkg() + '\nX: https://drive.google.com/a\n', 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('Drive' in issue for issue in issues)


def test_windows_pathext_cmd_resolution(monkeypatch, tmp_path):
    monkeypatch.setattr(qh.os, 'name', 'nt')
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.setenv('PATHEXT', '.COM;.EXE;.BAT;.CMD')
    f = tmp_path / 'npm.cmd'
    f.write_text('@echo off')
    resolved = qh.resolve_program('npm')
    assert resolved and resolved.lower().endswith('npm.cmd')
    cmd = qh.portable_command(['npm', '--version'])
    assert '/c' in [str(x).lower() for x in cmd]


def test_missing_executable_is_explicit(tmp_path):
    rc, out, duration = qh.execute(['definitely-missing-h3-command'], tmp_path, 1)
    assert rc == 127 and out and duration >= 0


def test_missing_harness_ref_rejected():
    text = pkg().replace(f'HARNESS_REF: {HARNESS_SHA}\n', '')
    issues = qh.validate_package_text(text, 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('HARNESS_REF' in issue for issue in issues)


def test_wrong_harness_ref_rejected():
    issues = qh.validate_package_text(pkg(), 'demo', 'QA-H3-demo-001', 'b' * 40)
    assert any('HARNESS_REF' in issue for issue in issues)


def test_untimed_created_at_rejected():
    text = pkg().replace(CREATED_AT, '2026-10-09T17:30:00')
    issues = qh.validate_package_text(text, 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('CREATED_AT' in issue for issue in issues)


def test_legacy_result_destination_rejected():
    text = pkg().replace('.tmp/qa/run/result/', '.tmp/qa/demo/QA-H3-demo-001/result/')
    issues = qh.validate_package_text(text, 'demo', 'QA-H3-demo-001', HARNESS_SHA)
    assert any('RESULT_DESTINATION' in issue for issue in issues)
