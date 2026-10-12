import importlib.util
import subprocess
import sys
from pathlib import Path

launcher_spec = importlib.util.spec_from_file_location(
    'qa_launcher', Path(__file__).resolve().parents[1] / 'tools/qa_launcher.py'
)
ql = importlib.util.module_from_spec(launcher_spec)
launcher_spec.loader.exec_module(ql)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_harness', ROOT / 'validators/validate_harness.py')
vh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vh)


def current_docs():
    docs, missing = vh.load_docs(ROOT)
    assert missing == []
    return docs


def test_validator_passes_current_contract():
    assert vh.validate_root(ROOT) == []


def test_qa_launcher_version():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/qa_launcher.py'), '--version'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == 'H3-QA-LAUNCHER-2'


def test_qa_launcher_materializes_assets_from_exact_commit(tmp_path):
    harness = tmp_path / 'harness'
    product = tmp_path / 'product'
    harness.mkdir()
    product.mkdir()

    def run_git(cwd, *args):
        return subprocess.run(
            ['git', *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    for repo_path in [harness, product]:
        run_git(repo_path, 'init')
        run_git(repo_path, 'config', 'user.email', 'qa@example.invalid')
        run_git(repo_path, 'config', 'user.name', 'QA Test')

    (harness / 'prompts').mkdir()
    (harness / 'tools').mkdir()
    (harness / 'prompts/QA_AGENT_MAIN_PROMPT.md').write_text('PINNED PROMPT\n', 'utf-8')
    (harness / 'tools/qa_harness.py').write_text('PINNED HELPER\n', 'utf-8')
    (harness / 'tools/qa_launcher.py').write_text('PINNED LAUNCHER\n', 'utf-8')
    run_git(harness, 'add', '.')
    run_git(harness, 'commit', '-m', 'pinned harness')
    harness_ref = run_git(harness, 'rev-parse', 'HEAD')

    (harness / 'prompts/QA_AGENT_MAIN_PROMPT.md').write_text('WORKTREE PROMPT\n', 'utf-8')
    (harness / 'tools/qa_harness.py').write_text('WORKTREE HELPER\n', 'utf-8')
    (harness / 'tools/qa_launcher.py').write_text('WORKTREE LAUNCHER\n', 'utf-8')

    (product / 'README.md').write_text('product\n', 'utf-8')
    run_git(product, 'add', '.')
    run_git(product, 'commit', '-m', 'product checkout')

    package = tmp_path / 'PACOTE_QA.txt'
    package.write_text(
        'QA_CONTRACT_VERSION: H3.0.0\n'
        'QA_ID: QA-H3-front-safe-002\n'
        'QA_PURPOSE: FORMAL\n'
        'front_id: front-safe\n'
        f'HARNESS_REF: {harness_ref}\n'
        'CREATED_AT: 2026-10-01T01:54:28-03:00\n'
        'REVISION_POLICY: BRANCH_CURRENT\n'
        'EXPECT_BRANCH: main\n'
        'EXPECT_HEAD: \n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n',
        'utf-8',
    )
    stale = product / '.tmp/qa/run/stale.txt'
    stale.parent.mkdir(parents=True)
    stale.write_text('stale', 'utf-8')

    manifest = ql.prepare_session(harness, package, product)

    assert not stale.exists()
    assert (product / '.tmp/qa/run/artifacts').is_dir()
    assert Path(manifest['package_file']).read_bytes() == package.read_bytes()
    assert Path(manifest['qa_launcher']).read_text('utf-8') == 'PINNED LAUNCHER\n'
    assert Path(manifest['qa_prompt']).read_text('utf-8') == 'PINNED PROMPT\n'
    assert Path(manifest['qa_helper']).read_text('utf-8') == 'PINNED HELPER\n'
    assert manifest['harness_ref'] == harness_ref
    assert manifest['legacy_product_helpers_allowed'] is False
    assert '.claude' not in manifest['qa_prompt']
    assert '.claude' not in manifest['qa_helper']


def test_qa_prompt_forbids_legacy_product_helpers():
    docs = current_docs()
    source = docs['prompts/QA_AGENT_MAIN_PROMPT.md']
    old = 'Os arquivos `.claude/commands/qa.md`, `.claude/qa/qa_harness.py` e quaisquer helpers `.claude/qa/*` existentes no checkout de produto são legado e não pertencem ao executor V3.'
    assert old in source
    docs['prompts/QA_AGENT_MAIN_PROMPT.md'] = source.replace(
        old,
        'Os helpers locais do produto podem ser usados como fallback.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('legacy product QA helpers' in issue for issue in issues)


def test_qa_launcher_cannot_fallback_to_product_legacy_helper():
    docs = current_docs()
    source = docs['tools/qa_launcher.py']
    docs['tools/qa_launcher.py'] = source + '\nLEGACY = ".claude/qa/qa_harness.py"\n'
    issues = vh.validate_docs(docs)
    assert any('legacy product-helper fallback path' in issue for issue in issues)


def test_qa_helper_version():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/qa_harness.py'), '--version'],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == 'H3.0.0'


def test_editorial_rewording_does_not_break_contract():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'A decisão material pertence ao operador.'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'A palavra final sobre decisões materiais permanece com o operador.',
        1,
    )
    assert vh.validate_docs(docs) == []


def test_shared_mode_capabilities_cannot_regress():
    docs = current_docs()
    source = docs['AGENTS.md']
    old = 'GESTÃO e EXECUÇÃO compartilham as mesmas capacidades técnicas e estão sujeitos aos mesmos gates.'
    assert old in source
    docs['AGENTS.md'] = source.replace(
        old,
        'GESTÃO e EXECUÇÃO usam capacidades técnicas e gates diferentes.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('shared technical capabilities' in issue or 'gates orthogonal' in issue for issue in issues)


def test_gestao_requires_critical_evaluation_for_new_direction():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'Toda nova direção relevante em GESTÃO recebe avaliação crítica explícita antes da materialização.'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'Somente direções consideradas arriscadas recebem avaliação crítica.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('critical evaluation' in issue for issue in issues)


def test_gestao_imperative_does_not_authorize_materialization():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'Por si só, não autoriza edição persistente, implementação ou outro efeito material.'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'Por si só, autoriza edição persistente, implementação e outros efeitos materiais.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('imperative can materialize' in issue for issue in issues)


def test_concordo_neither_materializes_nor_satisfies_gates():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'Não materializa, não muda o modo e não satisfaz gate independente.'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'Materializa a proposta e satisfaz o gate independente.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('CONCORDO can materialize' in issue for issue in issues)
    assert any('CONCORDO can satisfy a gate' in issue for issue in issues)


def test_autorizo_includes_technical_details_without_expanding_material_decision():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'O recorte autorizado inclui detalhes locais, reversíveis e tecnicamente equivalentes necessários para completar a ação'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'O recorte autorizado exclui detalhes locais, reversíveis e tecnicamente equivalentes necessários para completar a ação',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('technical-detail scope' in issue for issue in issues)


def test_new_material_decision_interrupts_only_dependent_scope_in_gestao():
    docs = current_docs()
    source = docs['Modos/GESTAO.md']
    old = 'Fato novo material interrompe somente o recorte dependente.'
    assert old in source
    docs['Modos/GESTAO.md'] = source.replace(
        old,
        'Fato novo material amplia automaticamente o escopo autorizado.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('dependent-scope interruption' in issue for issue in issues)


def test_execucao_with_plan_does_not_reconstruct_deliberation():
    docs = current_docs()
    source = docs['AGENTS.md']
    old = '- não reconstrua a deliberação que já está consolidada no PLAN ou em outra fonte proprietária;'
    assert old in source
    docs['AGENTS.md'] = source.replace(
        old,
        '- reconstrua toda a deliberação antes de executar a task;',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('EXECUCAO-with-plan focused routing' in issue for issue in issues)


def test_execucao_without_plan_does_not_require_artificial_plan():
    docs = current_docs()
    source = docs['Modos/EXECUCAO.md']
    old = 'PLAN formal não é pré-condição universal de EXECUÇÃO.'
    assert old in source
    docs['Modos/EXECUCAO.md'] = source.replace(
        old,
        'PLAN formal é pré-condição universal de EXECUÇÃO.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('requires a formal PLAN' in issue for issue in issues)


def test_gates_remain_orthogonal_across_modes():
    docs = current_docs()
    source = docs['GOVERNANCA.md']
    old = 'Os gates abaixo são ortogonais aos modos.'
    assert old in source
    docs['GOVERNANCA.md'] = source.replace(
        old,
        'Os gates abaixo variam conforme o modo.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('gates orthogonal' in issue for issue in issues)


def test_explicit_mode_change_must_persist_before_continuation():
    docs = current_docs()
    source = docs['OPERACAO_DOCUMENTAL.md']
    old = 'Uma diretiva explícita `MODO:` é persistida no ACTIVE antes de continuar o trabalho. O agente nunca muda o modo autonomamente.'
    assert old in source
    docs['OPERACAO_DOCUMENTAL.md'] = source.replace(
        old,
        'Uma diretiva explícita `MODO:` pode ficar só na conversa. O agente pode mudar o modo autonomamente.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('MODO persistence' in issue for issue in issues)
    assert any('autonomous mode switching' in issue for issue in issues)

def test_missing_essential_active_field_fails():
    docs = current_docs()
    source = docs['templates/FRONT_TEMPLATE.md']
    marker = 'Harness ref: <SHA exato da definição do harness>\n'
    assert marker in source
    docs['templates/FRONT_TEMPLATE.md'] = source.replace(marker, '', 1)
    issues = vh.validate_docs(docs)
    assert any('ACTIVE missing fields' in issue and 'Harness ref' in issue for issue in issues)


def test_topology_cannot_become_mandatory_by_accident():
    docs = current_docs()
    source = docs['templates/FRONT_TEMPLATE.md']
    marker = 'front_id: <front_id>\n'
    assert marker in source
    docs['templates/FRONT_TEMPLATE.md'] = source.replace(
        marker,
        marker + 'Frente-pai: <front_id>\n',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('topology mandatory' in issue for issue in issues)


def test_connector_recipe_leak_fails():
    docs = current_docs()
    docs['OPERACAO_DOCUMENTAL.md'] += '\nkeep_source_file_type\n'
    issues = vh.validate_docs(docs)
    assert any('connector recipe' in issue for issue in issues)


def test_obsolete_qa_mode_fails():
    docs = current_docs()
    source = docs['templates/PACOTE_QA_TEMPLATE.txt']
    assert 'QA_PURPOSE: FORMAL' in source
    docs['templates/PACOTE_QA_TEMPLATE.txt'] = source.replace(
        'QA_PURPOSE: FORMAL', 'QA_MODE: FORMAL', 1
    )
    issues = vh.validate_docs(docs)
    assert any('QA package' in issue for issue in issues)


def test_removed_helper_orchestration_command_fails_if_reintroduced():
    docs = current_docs()
    source = docs['tools/qa_harness.py']
    marker = 'sub = root.add_subparsers(dest="cmd", required=True)'
    assert marker in source
    docs['tools/qa_harness.py'] = source.replace(
        marker,
        marker + '\n    sub.add_parser("run-parallel")',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('obsolete commands' in issue and 'run-parallel' in issue for issue in issues)


def test_qa_package_requires_harness_ref():
    docs = current_docs()
    source = docs['templates/PACOTE_QA_TEMPLATE.txt']
    marker = 'HARNESS_REF: <SHA exato de 40 hex copiado do ACTIVE>\n'
    assert marker in source
    docs['templates/PACOTE_QA_TEMPLATE.txt'] = source.replace(marker, '', 1)
    issues = vh.validate_docs(docs)
    assert any('HARNESS_REF' in issue for issue in issues)


def test_qa_helper_rejects_package_harness_ref_mismatch():
    helper_path = ROOT / 'tools/qa_harness.py'
    spec = importlib.util.spec_from_file_location('qa_harness', helper_path)
    qh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qh)
    package = (
        'QA_CONTRACT_VERSION: H3.0.0\n'
        'QA_ID: QA-H3-front-safe-002\n'
        'QA_PURPOSE: FORMAL\n'
        'front_id: front-safe\n'
        'HARNESS_REF: ' + ('a' * 40) + '\n'
        'CREATED_AT: 2026-10-01T01:54:28-03:00\n'
        'REVISION_POLICY: BRANCH_CURRENT\n'
        'EXPECT_BRANCH: main\n'
        'EXPECT_HEAD: \n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n'
        + ''.join(f'[{section}]\nvalue\n' for section in qh.REQUIRED_SECTIONS)
    )
    issues = qh.validate_package_text(
        package,
        'front-safe',
        'QA-H3-front-safe-002',
        'b' * 40,
    )
    assert any('HARNESS_REF must match launcher harness ref' in issue for issue in issues)


def test_qa_package_requires_created_at_and_fixed_result_destination():
    docs = current_docs()
    source = docs['templates/PACOTE_QA_TEMPLATE.txt']
    created = 'CREATED_AT: <ISO 8601 com timezone, ex. 2026-10-01T01:54:28-03:00>\n'
    assert created in source
    docs['templates/PACOTE_QA_TEMPLATE.txt'] = source.replace(created, '', 1)
    issues = vh.validate_docs(docs)
    assert any('CREATED_AT' in issue for issue in issues)


def test_qa_helper_rejects_timestamp_without_timezone():
    helper_path = ROOT / 'tools/qa_harness.py'
    spec = importlib.util.spec_from_file_location('qa_harness_timestamp', helper_path)
    qh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qh)
    package = (
        'QA_CONTRACT_VERSION: H3.0.0\n'
        'QA_ID: QA-H3-front-safe-002\n'
        'QA_PURPOSE: FORMAL\n'
        'front_id: front-safe\n'
        'HARNESS_REF: ' + ('a' * 40) + '\n'
        'CREATED_AT: 2026-10-01T01:54:28\n'
        'REVISION_POLICY: BRANCH_CURRENT\n'
        'EXPECT_BRANCH: main\n'
        'EXPECT_HEAD: \n'
        'RESULT_DESTINATION: .tmp/qa/run/result/\n'
        + ''.join(f'[{section}]\nvalue\n' for section in qh.REQUIRED_SECTIONS)
    )
    issues = qh.validate_package_text(package, 'front-safe', 'QA-H3-front-safe-002', 'a' * 40)
    assert 'CREATED_AT must be ISO 8601 with timezone' in issues


def test_preflight_result_reset_preserves_session_artifacts(tmp_path):
    helper_path = ROOT / 'tools/qa_harness.py'
    spec = importlib.util.spec_from_file_location('qa_harness_reset', helper_path)
    qh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qh)
    product = tmp_path / 'product'
    artifacts = product / '.tmp/qa/run/artifacts'
    result = product / '.tmp/qa/run/result'
    artifacts.mkdir(parents=True)
    result.mkdir(parents=True)
    (artifacts / 'fixture.bin').write_text('keep', 'utf-8')
    (result / 'stale.log').write_text('remove', 'utf-8')

    qh.reset_result(product)

    assert (artifacts / 'fixture.bin').read_text('utf-8') == 'keep'
    assert not (result / 'stale.log').exists()
    assert (result / 'logs').is_dir()
    assert (result / 'screenshots').is_dir()



def test_front_id_storage_must_remain_flat():
    docs = current_docs()
    source = docs['templates/FRONT_TEMPLATE.md']
    marker = 'Nunca crie uma frente dentro da pasta de outra frente. Relação pai/filha é topologia lógica no ACTIVE/FRONT_TREE, não hierarquia física de pastas.'
    assert marker in source
    docs['templates/FRONT_TEMPLATE.md'] = source.replace(
        marker,
        'Frentes filhas podem ser criadas dentro da pasta da frente-pai.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('flat front_id/direct-child storage contract' in issue for issue in issues)


def test_operacao_forbids_child_folder_nesting():
    docs = current_docs()
    source = docs['OPERACAO_DOCUMENTAL.md']
    marker = '- frente filha nunca fica dentro da pasta da frente-pai;'
    assert marker in source
    docs['OPERACAO_DOCUMENTAL.md'] = source.replace(
        marker,
        '- frente filha pode ficar dentro da pasta da frente-pai;',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('flat front storage invariant' in issue for issue in issues)


def test_config_bootstrap_requires_single_segment_front_id():
    docs = current_docs()
    source = docs['CONFIGURACOES_PROJETO_CHATGPT.md']
    marker = 'São proibidos `/`, `\\\\`, `.`, `..` e qualquer forma que produza subdiretório.'
    assert marker in source
    docs['CONFIGURACOES_PROJETO_CHATGPT.md'] = source.replace(
        marker,
        'Barras podem representar hierarquia de frente.',
        1,
    )
    issues = vh.validate_docs(docs)
    assert any('flat front_id bootstrap invariant' in issue for issue in issues)
