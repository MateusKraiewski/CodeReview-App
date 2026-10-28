from pathlib import Path

import pytest

from crlocal import i18n
from crlocal.i18n import set_language
from crlocal.models import Severity
from crlocal.report import save, to_markdown
from crlocal.runner import run_review
from crlocal.skills import all_skills
from crlocal.skills.lizard_skill import ComplexitySkill, DuplicationSkill
from crlocal.skills.missing_tests import MissingTestsSkill
from crlocal.skills.patterns import PatternsSkill, load_rules

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "projeto-ruim"


@pytest.fixture(autouse=True)
def _pt():
    set_language("pt")
    yield
    set_language("pt")


def test_todas_as_traducoes_tem_tres_idiomas():
    for key, values in i18n._T.items():
        assert len(values) == 3 and all(values), key


def test_toda_skill_tem_titulo_traduzido():
    for lang in i18n.LANGUAGES:
        set_language(lang)
        for s in all_skills():
            assert s.title != f"skill.{s.id}.title"
            assert s.description != f"skill.{s.id}.desc"


def test_regras_yaml_carregam_com_tres_idiomas():
    rules = load_rules()
    assert rules
    for r in rules:
        assert isinstance(r["message"], dict) and set(r["message"]) == {"pt", "en", "es"}, r["id"]


def test_padroes_encontra_problemas_do_exemplo():
    rules = {f.rule_id for f in PatternsSkill().analyze(EXEMPLO, {"C#": 1, "Python": 1})}
    assert {"cs-catch-vazio", "cs-async-void", "cs-throw-ex", "cs-interface-sem-I"} <= rules


def test_complexidade_e_duplicacao(tmp_path):
    corpo = "\n".join(f"    if a > {i}:\n        x = a * {i} + 1\n        print(x)" for i in range(15))
    (tmp_path / "a.py").write_text(f"def f(a):\n{corpo}\n\ndef g(a):\n{corpo}\n", encoding="utf-8")
    assert any(f.rule_id == "complexidade-ciclomatica" for f in ComplexitySkill().analyze(tmp_path, {"Python": 1}))
    assert any(f.rule_id == "bloco-duplicado" for f in DuplicationSkill().analyze(tmp_path, {"Python": 1}))


def test_projeto_sem_testes():
    findings = MissingTestsSkill().analyze(EXEMPLO, {})
    assert findings[0].rule_id == "sem-testes" and findings[0].severity == Severity.ALTA


def test_skill_sem_ferramenta_e_pulada_sem_quebrar(monkeypatch):
    from crlocal.skills import gitleaks

    monkeypatch.setattr(gitleaks, "find_tool", lambda name: None)
    result = gitleaks.GitleaksSkill().execute(EXEMPLO, {"C#": 1})
    assert result.status == "skipped"


@pytest.mark.parametrize("lang,title", [("pt", "Relatório de Code Review"), ("en", "Code Review Report"),
                                        ("es", "Informe de Code Review")])
def test_relatorio_nos_tres_idiomas(lang, title, tmp_path):
    set_language(lang)
    skills = [s for s in all_skills() if s.id in {"padroes", "complexidade", "testes"}]
    report = run_review(EXEMPLO, skills)
    assert 0 <= report.score() < 100
    assert to_markdown(report).startswith(f"# {title}")
    files = save(report, tmp_path)
    assert {p.suffix for p in files} == {".md", ".pdf"}
    assert all(p.stat().st_size > 500 for p in files)
