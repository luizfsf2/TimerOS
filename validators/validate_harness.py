#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REQ = [
    'AGENTS.md',
    'GOVERNANCA.md',
    'OPERACAO_DOCUMENTAL.md',
    'CONFIGURACOES_PROJETO_CHATGPT.md',
    'README.md',
    'Modos/GESTAO.md',
    'Modos/EXECUCAO.md',
    'docs/RECUPERACAO_E_VERSIONAMENTO.md',
    'methodologies/PLANEJAMENTO_E_IMPLEMENTACAO.md',
    'methodologies/INTERFACE_E_VALIDACAO_VISUAL.md',
    'methodologies/QA_LOCAL.md',
    'prompts/QA_AGENT_MAIN_PROMPT.md',
    'templates/FRONT_TEMPLATE.md',
    'templates/PACOTE_QA_TEMPLATE.txt',
    'tools/qa_harness.py',
    'tools/qa_launcher.py',
]

ACTIVE_FIELDS = {
    'front_id', 'Status', 'Modo', 'Harness ref', 'Branch', 'HEAD observado',
    'Tarefa corrente', 'QA atual', 'Atualização',
}
TOPOLOGY_FIELDS = {'Frente-pai', 'Origem no pai', 'Retorno ao concluir'}
QA_HEADER_FIELDS = {
    'QA_CONTRACT_VERSION', 'QA_ID', 'QA_PURPOSE', 'front_id', 'HARNESS_REF',
    'CREATED_AT', 'REVISION_POLICY', 'EXPECT_BRANCH', 'EXPECT_HEAD', 'RESULT_DESTINATION',
}
QA_SECTIONS = {
    'OBJECTIVE', 'CONTEXT', 'DECISIONS', 'DELTA', 'RISKS',
    'EXPECTED_BEHAVIOR', 'TESTS_ALREADY_RUN', 'SCOPE', 'LIMITS',
    'RETURN_CONTRACT',
}
QA_COMMANDS = {'validate-package', 'preflight', 'workspace', 'run', 'finalize'}
FORBIDDEN_QA_COMMANDS = {'run-parallel', 'delta', 'report-block'}


def load_docs(root: Path) -> tuple[dict[str, str], list[str]]:
    docs: dict[str, str] = {}
    issues: list[str] = []
    for rel in REQ:
        path = root / rel
        if not path.is_file():
            issues.append(f'missing file: {rel}')
            continue
        docs[rel] = path.read_text('utf-8', errors='replace')
    return docs, issues


def fenced_blocks(text: str, language: str | None = None) -> list[str]:
    if language is None:
        pattern = r'```[^\n]*\n(.*?)```'
    else:
        pattern = rf'```{re.escape(language)}\s*\n(.*?)```'
    return re.findall(pattern, text, flags=re.S | re.I)


def field_names(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        match = re.match(r'^\s*([A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ0-9 _-]*?)\s*:', line)
        if match:
            out.add(match.group(1).strip())
    return out


def headings(text: str) -> list[str]:
    return [m.group(2).strip().casefold() for m in re.finditer(r'(?m)^(#{1,6})\s+(.+?)\s*$', text)]


def has_heading(text: str, *words: str) -> bool:
    wanted = [w.casefold() for w in words]
    return any(all(word in heading for word in wanted) for heading in headings(text))


def heading_section(text: str, level: int, *words: str) -> str:
    wanted = [w.casefold() for w in words]
    lines = text.splitlines(keepends=True)
    prefix = '#' * level + ' '
    start = None
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        title = line[len(prefix):].strip().casefold()
        if all(word in title for word in wanted):
            start = index + 1
            break
    if start is None:
        return ''
    end = len(lines)
    for index in range(start, len(lines)):
        match = re.match(r'^(#{1,6})\s+', lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return ''.join(lines[start:end])


def require(condition: bool, label: str, issues: list[str]) -> None:
    if not condition:
        issues.append(label)


def qa_helper_subcommands(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != 'add_parser' or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.add(arg.value)
    return out


def validate_docs(docs: dict[str, str]) -> list[str]:
    issues: list[str] = []
    alltext = '\n'.join(docs.values())

    if re.search(r'(?i)AUTONOMY_OVERRIDE\s*[:=]\s*(?:true|1|yes|sim|enabled)', alltext):
        issues.append('forbidden enabled AUTONOMY_OVERRIDE')
    if re.search(r'(?i)\b(?:execute|faça|fazer|use)\s+git\s+pull\b', alltext):
        issues.append('forbidden operational git pull instruction')

    agents = docs.get('AGENTS.md', '')
    for owner in [
        'Modos/GESTAO.md', 'Modos/EXECUCAO.md', 'GOVERNANCA.md',
        'OPERACAO_DOCUMENTAL.md', 'methodologies/QA_LOCAL.md',
        'templates/FRONT_TEMPLATE.md', 'templates/PACOTE_QA_TEMPLATE.txt',
        'tools/qa_launcher.py', 'docs/RECUPERACAO_E_VERSIONAMENTO.md',
    ]:
        require(owner in agents, f'AGENTS missing owner route: {owner}', issues)
    require('Harness ref' in agents and 'ACTIVE' in agents, 'AGENTS missing per-front harness pinning', issues)
    require('HARNESS_REF =' not in agents, 'AGENTS defines a global HARNESS_REF', issues)
    require(
        re.search(r'(?is)GESTÃO.{0,80}EXECUÇÃO.{0,180}mesmas capacidades técnicas', agents) is not None
        and re.search(r'(?is)mesm(?:os|as).{0,40}gates', agents) is not None,
        'AGENTS missing shared technical capabilities across modes',
        issues,
    )

    cfg = docs.get('CONFIGURACOES_PROJETO_CHATGPT.md', '')
    require('HARNESS_REPOSITORY' in cfg and 'WORKSPACE_ROOT' in cfg, 'CONFIG missing bootstrap locators', issues)
    require(not re.search(r'(?m)^\s*HARNESS_REF\s*=', cfg), 'CONFIG defines global HARNESS_REF', issues)
    require('Harness ref:' in cfg and 'ACTIVE.md' in cfg, 'CONFIG missing per-front Harness ref bootstrap', issues)
    require(
        r'São proibidos `/`, `\\`, `.`, `..` e qualquer forma que produza subdiretório.' in cfg
        and '^[A-Za-z0-9][A-Za-z0-9._-]*$' in cfg
        and 'filha imediata' in cfg.casefold()
        and re.search(r'(?is)nunca.{0,120}nesting físico', cfg) is not None,
        'CONFIG missing flat front_id bootstrap invariant',
        issues,
    )
    require('mirror obrigatório' in cfg.casefold() or 'mirror obrigatorio' in cfg.casefold(), 'CONFIG does not state mirror is optional/not required', issues)

    front = docs.get('templates/FRONT_TEMPLATE.md', '')
    markdown_blocks = fenced_blocks(front, 'markdown')
    require(bool(markdown_blocks), 'FRONT_TEMPLATE missing markdown example blocks', issues)
    if markdown_blocks:
        active_fields = field_names(markdown_blocks[0])
        missing = sorted(ACTIVE_FIELDS - active_fields)
        if missing:
            issues.append('FRONT_TEMPLATE ACTIVE missing fields: ' + ', '.join(missing))
        mandatory_topology = sorted(TOPOLOGY_FIELDS & active_fields)
        if mandatory_topology:
            issues.append('FRONT_TEMPLATE makes topology mandatory in base ACTIVE: ' + ', '.join(mandatory_topology))
        topology_elsewhere = set().union(*(field_names(block) for block in markdown_blocks[1:])) if len(markdown_blocks) > 1 else set()
        require({'Frente-pai', 'Origem no pai'} <= topology_elsewhere, 'FRONT_TEMPLATE missing optional child topology block', issues)
    require('Retorno ao concluir' in front, 'FRONT_TEMPLATE missing exceptional return field', issues)
    require(
        '^[A-Za-z0-9][A-Za-z0-9._-]*$' in front
        and 'filho imediato' in front.casefold()
        and re.search(r'(?is)nunca.{0,100}frente.{0,100}dentro.{0,100}pasta.{0,100}outra frente', front) is not None,
        'FRONT_TEMPLATE missing flat front_id/direct-child storage contract',
        issues,
    )
    require('CHECKLIST.md' not in front or re.search(r'(?i)(não|nao).{0,30}CHECKLIST', front) is not None,
            'FRONT_TEMPLATE requires CHECKLIST', issues)

    gestao = docs.get('Modos/GESTAO.md', '')
    gestao_commands = heading_section(gestao, 2, 'comandos', 'materialização')
    require('CONCORDO' in gestao and 'AUTORIZO' in gestao, 'GESTAO missing concordance/authorization boundary', issues)
    require(re.search(r'(?i)materializa', gestao) is not None, 'GESTAO missing materialization boundary', issues)
    require(
        re.search(r'(?is)\b(?:toda|cada)\b.{0,60}\bdireção\b.{0,180}\bavaliação crítica\b', gestao) is not None,
        'GESTAO missing universal proportional critical evaluation',
        issues,
    )
    require(
        re.search(r'(?is)(pedido|imperativo).{0,220}por si só.{0,80}não autoriza', gestao_commands) is not None,
        'GESTAO imperative can materialize without AUTORIZO',
        issues,
    )
    require(
        re.search(r'(?is)CONCORDO.{0,260}não materializa', gestao_commands) is not None,
        'GESTAO CONCORDO can materialize',
        issues,
    )
    require(
        re.search(r'(?is)CONCORDO.{0,320}não satisfaz.{0,80}gate', gestao_commands) is not None,
        'GESTAO CONCORDO can satisfy a gate',
        issues,
    )
    require(
        re.search(r'(?is)AUTORIZO.{0,260}autoriza.{0,160}materializa', gestao_commands) is not None,
        'GESTAO AUTORIZO missing materialization semantics',
        issues,
    )
    require(
        re.search(r'(?is)recorte autorizado.{0,100}inclui.{0,220}(detalhes locais|microdecis)', gestao_commands) is not None,
        'GESTAO AUTORIZO missing technical-detail scope',
        issues,
    )
    require(
        re.search(r'(?is)(fato novo material|decisão material nova).{0,180}interrompe.{0,120}recorte dependente', gestao_commands) is not None,
        'GESTAO missing dependent-scope interruption for new material decision',
        issues,
    )

    execucao = docs.get('Modos/EXECUCAO.md', '')
    require(re.search(r'(?i)microdecis', execucao) is not None, 'EXECUCAO missing technical microdecision autonomy', issues)
    require(re.search(r'(?i)(fato novo|nova decisão material)', execucao) is not None, 'EXECUCAO missing material-change interruption rule', issues)
    require(
        re.search(r'(?is)PLAN formal.{0,100}não (?:é|e) pré-condição universal', execucao) is not None,
        'EXECUCAO requires a formal PLAN',
        issues,
    )
    require(
        re.search(r'(?is)pedido explícito.{0,220}ações não gated', execucao) is not None
        and re.search(r'(?is)não é exigido.{0,100}AUTORIZO', execucao) is not None,
        'EXECUCAO missing direct-request authorization semantics',
        issues,
    )
    require('methodologies/QA_LOCAL.md' in execucao, 'EXECUCAO missing QA owner link', issues)
    require('QA_MODE' not in execucao, 'EXECUCAO references obsolete QA_MODE', issues)

    gestao_route = heading_section(agents, 3, 'gestão')
    exec_plan_route = heading_section(agents, 3, 'execução', 'plano formal')
    exec_no_plan_route = heading_section(agents, 3, 'execução', 'sem plano formal')
    require(
        gestao_route
        and re.search(r'(?is)AUTORIZO.{0,360}(sem reconstruir|não reconstr)', gestao_route) is not None
        and re.search(r'(?is)(microdecis|confirmação por arquivo)', gestao_route) is not None,
        'AGENTS missing post-AUTORIZO technical-detail routing in GESTAO',
        issues,
    )
    require(
        exec_plan_route
        and re.search(r'(?is)task corrente', exec_plan_route) is not None
        and re.search(r'(?is)não reconstrua.{0,120}deliberação', exec_plan_route) is not None,
        'AGENTS missing EXECUCAO-with-plan focused routing',
        issues,
    )
    require(
        exec_no_plan_route
        and re.search(r'(?is)solicitação explícita', exec_no_plan_route) is not None
        and re.search(r'(?is)não (?:crie|expanda|leia).{0,120}PLAN.{0,160}cerimônia', exec_no_plan_route) is not None,
        'AGENTS missing EXECUCAO-without-plan routing',
        issues,
    )

    gov = docs.get('GOVERNANCA.md', '')
    for words in [('papel', 'autoridade'), ('legado',), ('gates',), ('segurança',), ('evidência',), ('beta', 'release')]:
        require(has_heading(gov, *words), f'GOVERNANCA missing section: {"/".join(words)}', issues)
    for concept, pattern in [
        ('branch', r'(?i)criar branch'),
        ('merge', r'(?i)\bmerge\b'),
        ('PR', r'(?i)\bPR\b'),
        ('CI', r'(?i)(GitHub Actions|\bCI\b)'),
        ('backlog', r'(?i)(TODO|IDEIAS)'),
        ('BETA', r'\bBETA\b'),
        ('release', r'(?i)\brelease\b'),
        ('migration/shared mutation', r'(?i)(migration|banco|runtime|infraestrutura compartilhad)'),
        ('cost', r'(?i)custo recorrente'),
    ]:
        require(re.search(pattern, gov) is not None, f'GOVERNANCA missing gate concept: {concept}', issues)
    for forbidden in ['REVISION_POLICY', 'OPERATOR_ACTION_REQUIRED', '.tmp/qa/']:
        require(forbidden not in gov, f'GOVERNANCA owns QA protocol detail: {forbidden}', issues)
    require(
        re.search(r'(?is)gates.{0,120}ortogonais.{0,180}GESTÃO.{0,100}EXECUÇÃO', gov) is not None,
        'GOVERNANCA does not keep gates orthogonal across modes',
        issues,
    )

    op = docs.get('OPERACAO_DOCUMENTAL.md', '')
    for marker in ['text/markdown', 'text/plain', 'readback', 'igualdade integral', 'idempot', 'amplificação']:
        require(marker.casefold() in op.casefold(), f'OPERACAO missing raw-write invariant: {marker}', issues)
    for forbidden in ['keep_source_file_type', 'update_file', 'file_uri', 'U+000B']:
        require(forbidden not in op, f'OPERACAO leaks connector recipe: {forbidden}', issues)
    require(re.search(r'(?i)topologia opcional', op) is not None, 'OPERACAO missing optional topology contract', issues)
    require(
        '^[A-Za-z0-9][A-Za-z0-9._-]*$' in op
        and 'filho imediato' in op.casefold()
        and 'frente filha nunca fica dentro da pasta da frente-pai' in op.casefold()
        and 'derivação lógica não cria hierarquia física' in op.casefold(),
        'OPERACAO missing flat front storage invariant',
        issues,
    )
    require('FRONT_TREE.md' in op and re.search(r'(?i)(derivad|índice navegacional)', op) is not None,
            'OPERACAO missing derived FRONT_TREE contract', issues)
    require(re.search(r'(?i)checkup', op) is not None and re.search(r'(?i)(contador|watchdog)', op) is not None,
            'OPERACAO missing bounded checkup contract', issues)
    require(
        re.search(r'(?is)diretiva explícita.{0,80}MODO.{0,160}persistid.{0,100}ACTIVE.{0,100}antes de continuar', op) is not None,
        'OPERACAO missing explicit MODO persistence before continuation',
        issues,
    )
    require(
        re.search(r'(?is)(nunca|não).{0,80}muda.{0,80}modo.{0,80}autonom', op) is not None,
        'OPERACAO allows autonomous mode switching',
        issues,
    )

    qa = docs.get('methodologies/QA_LOCAL.md', '')
    for marker in ['CHECKPOINT', 'FORMAL', 'EXACT', 'BRANCH_CURRENT', 'OPERATOR_ACTION_REQUIRED', 'QA_ID', 'HARNESS_REF', 'CREATED_AT', '.tmp/qa/run/']:
        require(marker in qa, f'QA_LOCAL missing contract marker: {marker}', issues)
    require('QA_MODE' not in qa, 'QA_LOCAL references obsolete QA_MODE', issues)
    require(re.search(r'(?i)não corrige produto|não alterar produto', qa) is not None, 'QA_LOCAL missing no-product-fix boundary', issues)

    package = docs.get('templates/PACOTE_QA_TEMPLATE.txt', '')
    header_fields = field_names(package)
    missing_header = sorted(QA_HEADER_FIELDS - header_fields)
    if missing_header:
        issues.append('QA package missing header fields: ' + ', '.join(missing_header))
    sections = set(re.findall(r'(?m)^\[([A-Z_]+)\]\s*$', package))
    missing_sections = sorted(QA_SECTIONS - sections)
    if missing_sections:
        issues.append('QA package missing sections: ' + ', '.join(missing_sections))
    require('QA_MODE' not in package, 'QA package references obsolete QA_MODE', issues)
    require(re.search(r'(?m)^HARNESS_REF:\s*<SHA exato', package) is not None,
            'QA package template does not require exact HARNESS_REF', issues)
    require(re.search(r'(?m)^CREATED_AT:\s*<ISO 8601', package) is not None,
            'QA package template does not require CREATED_AT', issues)
    require('RESULT_DESTINATION: .tmp/qa/run/result/' in package,
            'QA package template does not use fixed run result destination', issues)

    helper = docs.get('tools/qa_harness.py', '')
    commands = qa_helper_subcommands(helper)
    missing_commands = sorted(QA_COMMANDS - commands)
    if missing_commands:
        issues.append('qa_harness missing commands: ' + ', '.join(missing_commands))
    obsolete_commands = sorted(FORBIDDEN_QA_COMMANDS & commands)
    if obsolete_commands:
        issues.append('qa_harness exposes obsolete commands: ' + ', '.join(obsolete_commands))
    require('QA_PURPOSE' in helper and 'QA_MODE' not in helper, 'qa_harness package purpose contract is stale', issues)
    require('HARNESS_REF' in helper and '--harness-ref' in helper,
            'qa_harness does not bind package HARNESS_REF to launcher identity', issues)
    require('CREATED_AT' in helper and 'RESULT_DESTINATION = ".tmp/qa/run/result/"' in helper,
            'qa_harness missing timestamp/fixed result contract', issues)
    require('reset_result(product)' in helper and 'result_root(product)' in helper,
            'qa_harness missing preflight result reset', issues)
    for section in QA_SECTIONS:
        require(section in helper, f'qa_harness does not validate section: {section}', issues)

    launcher = docs.get('tools/qa_launcher.py', '')
    for marker in [
        'HARNESS_REF', 'CREATED_AT', 'prompts/QA_AGENT_MAIN_PROMPT.md', 'tools/qa_harness.py',
        '--product-worktree', '--package-file', '.tmp/qa/run', 'reset_session', 'git', 'show',
    ]:
        require(marker in launcher, f'QA launcher missing pin-safe marker: {marker}', issues)
    require('.claude/qa/qa_harness.py' not in launcher and '.claude/commands/qa.md' not in launcher,
            'QA launcher contains legacy product-helper fallback path', issues)
    require('legacy_product_helpers_allowed' in launcher and 'False' in launcher,
            'QA launcher does not explicitly forbid legacy product helpers', issues)

    prompt = docs.get('prompts/QA_AGENT_MAIN_PROMPT.md', '')
    require('QA_MODE' not in prompt, 'QA prompt references obsolete QA_MODE', issues)
    require('run-parallel' not in prompt and 'SLOW_FINAL' not in prompt, 'QA prompt exposes removed orchestration protocol', issues)
    require('OPERATOR_ACTION_REQUIRED' in prompt and 'mesm' in prompt.casefold(), 'QA prompt missing same-round recovery path', issues)
    require('HARNESS_REF' in prompt and 'LAUNCH.json' in prompt,
            'QA prompt missing HARNESS_REF/package-to-launch binding', issues)
    require('CREATED_AT' in prompt and '.tmp/qa/run/result/' in prompt and '.tmp/qa/run/artifacts/' in prompt,
            'QA prompt missing timestamp/fixed workspace contract', issues)
    require(
        '.claude/commands/qa.md' in prompt
        and '.claude/qa/' in prompt
        and 'legado' in prompt.casefold()
        and re.search(r'(?is)não.{0,100}(execute|importe|fallback)', prompt) is not None,
        'QA prompt does not forbid legacy product QA helpers for V3',
        issues,
    )

    require(re.search(r'(?i)helpers?\s+locais?.{0,80}\bfallback\b', prompt) is None,
            'legacy product QA helpers fallback is forbidden', issues)

    recovery = docs.get('docs/RECUPERACAO_E_VERSIONAMENTO.md', '')
    require('Harness ref' in recovery and 'branch `harness`' in recovery, 'recovery missing pinning/maintenance model', issues)
    require('mirror obrigatório' in recovery.casefold() or 'mirror obrigatorio' in recovery.casefold(),
            'recovery does not state mirror is optional/not required', issues)

    readme = docs.get('README.md', '')
    require('Harness ref:' in readme and 'WORKSPACE_ROOT/tmp/' in readme, 'README missing Git/Drive boundary', issues)
    require('validators/' in readme and 'tests/' in readme, 'README missing local validation surface', issues)

    return issues


def validate_root(root: Path) -> list[str]:
    docs, issues = load_docs(root)
    issues.extend(validate_docs(docs))
    return issues


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
    issues = validate_root(root)
    if issues:
        for issue in issues:
            print('FAIL:', issue)
        return 1
    print('PASS: harness structural invariants')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
