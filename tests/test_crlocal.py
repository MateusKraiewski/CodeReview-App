import re
import shutil
import subprocess  # nosec B404 (os testes criam repositórios git temporários)
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from crlocal import i18n, mcp_server, sarif, updater
from crlocal.changes import ChangesError, resolve_scope
from crlocal.control import RunControl
from crlocal.dedupe import merge_duplicates
from crlocal.i18n import set_language
from crlocal.ignore import load as load_ignore
from crlocal.models import Finding, Severity
from crlocal.report import save, to_markdown
from crlocal.runner import run_review
from crlocal.skills import all_skills, gitleaks
from crlocal.skills.bandit_skill import _is_test
from crlocal.skills.base import Skill
from crlocal.skills.lizard_skill import ComplexitySkill, DuplicationSkill
from crlocal.skills.missing_tests import MissingTestsSkill
from crlocal.skills.patterns import PatternsSkill, load_rules
from crlocal.tools import run
from crlocal.updater import is_newer, parse_release, parse_version

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


def test_comparacao_de_versoes():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("0.1.0-dev.7") == (0, 1, 0)
    assert is_newer("v0.2.0", "0.1.9")
    assert is_newer("1.0.0", "0.9.9")
    assert not is_newer("v0.1.0", "0.1.0")
    assert not is_newer("0.1.0", "0.2.0")
    assert is_newer("v0.1.0", "0.1.0-dev.9")  # build de teste recebe a versão final
    assert not is_newer("0.1.0-dev.9", "0.1.0")


def test_le_release_do_github():
    data = {"tag_name": "v0.3.0", "html_url": "https://github.com/x/y/releases/tag/v0.3.0", "body": "notas",
            "assets": [{"name": "CodeReviewLocal-0.3.0-portatil.zip", "browser_download_url": "zip"},
                       {"name": "CodeReviewLocal-Setup-0.3.0.exe", "browser_download_url": "https://x/setup.exe"}]}
    u = parse_release(data)
    assert (u.version, u.setup_url, u.notes) == ("0.3.0", "https://x/setup.exe", "notas")


def test_sem_internet_nao_quebra(monkeypatch):


    def falha(*_a, **_k):
        raise OSError("sem rede")

    monkeypatch.setattr(urllib.request, "urlopen", falha)
    assert updater.check() is None


def test_sarif_e_problemas():
    root = Path(__file__).resolve().parent.parent / "exemplos" / "projeto-ruim"
    report = run_review(root, [s for s in all_skills() if s.id == "padroes"])
    doc = sarif.to_sarif(report)
    run = doc["runs"][0]
    assert doc["version"] == "2.1.0"
    assert len(run["results"]) == len(report.findings) > 0
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert all(r["ruleId"] in rule_ids for r in run["results"])
    lines = sarif.problem_lines(report)
    pattern = re.compile(r"^(.*):(\d+):(\d+): (error|warning|info): (.*)$")
    assert lines and all(pattern.match(line) for line in lines)


def test_mcp_server():
    init = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2025-03-26"}})
    assert init["result"]["protocolVersion"] == "2025-03-26"
    assert mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = {t["name"] for t in mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]}
    assert names == {"code_review", "achados", "listar_skills"}

    root = str(Path(__file__).resolve().parent.parent / "exemplos" / "projeto-ruim")
    call = mcp_server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "code_review", "arguments": {"pasta": root, "skills": ["padroes"], "salvar_relatorio": False}}})
    assert not call["result"]["isError"]
    assert "Nota:" in call["result"]["content"][0]["text"]

    det = mcp_server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
        "name": "achados", "arguments": {"pasta": root, "severidade_minima": "alta"}}})
    assert "achado(s)" in det["result"]["content"][0]["text"]

    bad = mcp_server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "xyz"}})
    assert bad["error"]["code"] == -32602


@pytest.mark.skipif(not shutil.which("git"), reason="git não instalado")
def test_revisar_so_alteracoes(tmp_path):


    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *args],  # nosec B603 B607
                       check=True, capture_output=True)

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("# TODO: antigo\n", encoding="utf-8")
    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", "init")
    git("checkout", "-qb", "feat")
    (tmp_path / "a.py").write_text("x = 1  # TODO: novo\n", encoding="utf-8")

    skills = [PatternsSkill()]
    local = resolve_scope(tmp_path, "local")
    assert local.files == {"a.py"}
    rep = run_review(tmp_path, skills, scope=local)
    assert {f.file for f in rep.findings} == {"a.py"} and rep.scope
    git("commit", "-qam", "muda a")
    with pytest.raises(ChangesError):
        run_review(tmp_path, skills, scope=resolve_scope(tmp_path, "local"))
    branch = resolve_scope(tmp_path, "branch")
    assert branch.base == "main" and branch.files == {"a.py"}
    assert {f.file for f in run_review(tmp_path, skills).findings} == {"a.py", "b.py"}


def test_pular_pausar_concluir(tmp_path):


    class Lenta(Skill):
        category = "Padrões"

        def __init__(self, sid):
            self.id = sid

        @property
        def title(self):
            return self.id

        def analyze(self, root, languages):
            run([sys.executable, "-c", "import time; time.sleep(30)"])
            return [self.finding(rule_id="x", message="x", severity=Severity.BAIXA, file="a.py")]

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    ctl = RunControl()
    t0 = time.monotonic()
    threading.Timer(0.5, ctl.skip, args=("lenta-1",)).start()
    threading.Timer(1.0, ctl.finish).start()
    rep = run_review(tmp_path, [Lenta("lenta-1"), Lenta("lenta-2")], control=ctl, workers=2)
    assert time.monotonic() - t0 < 15  # sem o controle levaria 30s
    status = {r.skill: (r.status, r.message) for r in rep.results}
    assert status["lenta-1"] == ("skipped", i18n.t("skip.user"))
    assert status["lenta-2"] == ("skipped", i18n.t("skip.finished"))
    assert not rep.findings

    ctl = RunControl()
    ctl.pause()
    threading.Timer(1.5, ctl.resume).start()
    t0 = time.monotonic()
    rep = run_review(tmp_path, [PatternsSkill()], control=ctl)
    assert time.monotonic() - t0 >= 1.4 and rep.results[0].status == "ok"


def test_crlocalignore_e_pastas_de_build(tmp_path):
    proj = tmp_path / "app"
    (proj / "exemplos").mkdir(parents=True)
    (proj / "build").mkdir()
    (proj / "src").mkdir()
    (proj / ".crlocalignore").write_text("# exemplo ruim de propósito\nexemplos/\n*.gerado.py\n", encoding="utf-8")
    for f in ("exemplos/ruim.py", "build/x.py", "src/ok.py", "src/x.gerado.py"):
        (proj / f).write_text("# TODO: algo\n", encoding="utf-8")
    # o .crlocalignore vale também quando a pasta analisada é a de cima
    rules = load_ignore(tmp_path)
    assert rules.ignored("app/exemplos/ruim.py") and rules.ignored("app/build/x.py")
    assert rules.ignored("app/src/x.gerado.py") and not rules.ignored("app/src/ok.py")
    assert not rules.ignored("exemplos/fora.py")  # o padrão só vale abaixo da pasta do .crlocalignore
    rep = run_review(tmp_path, [PatternsSkill()])
    assert {f.file for f in rep.findings} == {"app/src/ok.py"}


def test_bandit_ignora_assert_em_teste():
    assert _is_test("projeto/tests/test_algo.py") and _is_test("conftest.py")
    assert not _is_test("projeto/src/algo.py")


def test_achado_repetido_na_mesma_linha_aparece_uma_vez():
    def achado():
        return Finding(skill="seguranca-devskim", rule_id="DS126858", message="Weak/Broken Hash Algorithm",
                       severity=Severity.ALTA, file="a.py", line=3, category="Segurança")
    assert len(merge_duplicates([achado(), achado()])) == 1
