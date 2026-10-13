"""Verificações estáticas do contrato de planejamento da V3 (sem dependências externas)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8-sig")

class FeaturePlanningContractTests(unittest.TestCase):
    def test_feature_checklist_has_nine_dimensions(self):
        planning = read("methodologies/PLANEJAMENTO_E_IMPLEMENTACAO.md")
        expected = ["Problema e objetivo", "Investigação do existente", "Reuso e duplicidade",
                    "Requisitos e decisões vigentes", "Alternativas e boas práticas",
                    "Análise de impacto", "Preservação e regressões", "Plano incremental",
                    "Critérios de aceite"]
        for number, item in enumerate(expected, 1):
            with self.subTest(dimension=number):
                self.assertIn(f"{number}. **{item}:**", planning)

    def test_modes_have_same_gates_and_no_extra_authorization(self):
        gestao = read("Modos/GESTAO.md")
        execucao = read("Modos/EXECUCAO.md")
        gov = read("GOVERNANCA.md")
        self.assertIn("mesmos gates", gestao)
        self.assertIn("mesmos gates", execucao)
        self.assertIn("não podem acrescentar autorização operacional", gov)
        self.assertNotIn("para materialização durável em GESTÃO, obter", gestao)
        self.assertIn("sem exigir a palavra `AUTORIZO`", gestao)

    def test_planning_only_in_gestao(self):
        agents = read("AGENTS.md")
        gestao = agents.split("### GESTÃO — planejador/consultor", 1)[1].split(
            "### EXECUÇÃO com plano formal aplicável", 1)[0]
        execucao = agents.split("### EXECUÇÃO com plano formal aplicável", 1)[1].split(
            "### Bootstrap de QA V3", 1)[0]
        self.assertIn("checklist interno proporcional", gestao)
        self.assertIn("sem carregar o checklist consultivo", execucao)
        self.assertNotIn("depois de `AUTORIZO`", agents)
        self.assertIn("Não criar `CHECKLIST.md`", read("methodologies/PLANEJAMENTO_E_IMPLEMENTACAO.md"))

    def test_explicit_request_distinguished_from_consultation(self):
        gestao = read("Modos/GESTAO.md")
        self.assertIn("Pedido de análise, revisão, planejamento ou opinião", gestao)
        self.assertIn("Pedido explícito para implementar", gestao)
        self.assertIn("não apaga", gestao)

if __name__ == "__main__":
    unittest.main()
