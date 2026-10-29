"""Servidor MCP (Model Context Protocol) via stdio, sem dependências externas.

Permite que assistentes de IA nas IDEs (Claude Code, GitHub Copilot no VS Code, Cursor, Windsurf...)
chamem o code review local. A análise roda inteira na máquina, sem gastar tokens. A IA recebe só um
resumo compacto, e pode pedir mais detalhes com `achados` quando precisar.

Uso: CodeReviewLocal.exe --mcp   (ou: python -m crlocal --mcp)
"""
from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

from . import __version__
from . import report as report_mod
from . import sarif
from .changes import resolve_scope
from .i18n import LANGUAGES, set_language
from .models import Report, Severity
from .runner import run_review
from .skills import all_skills
from .tools import ensure_std_streams

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
TOP_N = 15
MAX_FINDINGS = 200

_last: dict[str, Report] = {}

TOOLS = [
    {
        "name": "code_review",
        "description": (
            "Faz o code review local (offline, sem IA) de uma pasta de projeto com ferramentas como Gitleaks, "
            "Semgrep, Bandit, Ruff, Roslyn (C#), Lizard e regras do time. Devolve nota 0-100, contagem por "
            "severidade, os achados mais graves e o caminho do relatório PDF/Markdown. Use 'achados' para "
            "ver mais itens sem rodar de novo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pasta": {"type": "string", "description": "Caminho absoluto da pasta do projeto."},
                "skills": {"type": "array", "items": {"type": "string"},
                           "description": "Ids das skills (veja 'listar_skills'). Padrão: todas."},
                "idioma": {"type": "string", "enum": list(LANGUAGES), "description": "Idioma do resultado."},
                "escopo": {"type": "string", "enum": ["tudo", "local", "branch"],
                           "description": ("tudo = projeto inteiro (padrão); local = só alterações não commitadas; "
                                           "branch = só o que mudou na branch em relação à base. Use local/branch "
                                           "para revisar de novo depois de corrigir.")},
                "base": {"type": "string", "description": "Branch base do escopo 'branch' (padrão: main/master)."},
                "salvar_relatorio": {"type": "boolean",
                                     "description": "Gerar PDF e Markdown em <pasta>/.codereview (padrão: true)."},
            },
            "required": ["pasta"],
        },
    },
    {
        "name": "achados",
        "description": ("Lista achados do último code review de uma pasta, com filtros, para inspecionar ou "
                        "corrigir. Rode 'code_review' antes."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pasta": {"type": "string", "description": "A mesma pasta usada no code_review."},
                "severidade_minima": {"type": "string", "enum": ["critica", "alta", "media", "baixa", "info"]},
                "arquivo": {"type": "string", "description": "Filtra por trecho do caminho do arquivo."},
                "skill": {"type": "string", "description": "Filtra por id da skill."},
                "limite": {"type": "integer", "minimum": 1, "maximum": MAX_FINDINGS},
            },
            "required": ["pasta"],
        },
    },
    {
        "name": "listar_skills",
        "description": "Lista as skills de code review disponíveis (id, categoria e descrição).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _key(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def _fmt(f) -> str:
    loc = f"{f.file}:{f.line}" if f.file and f.line else (f.file or "(projeto)")
    sug = f" → {f.suggestion}" if f.suggestion else ""
    return f"- [{f.severity.label}] {loc} · {f.rule_id} ({f.skill}): {f.message}{sug}"[:400]


def tool_code_review(args: dict) -> str:
    set_language(args.get("idioma") or "pt")
    root = Path(args["pasta"]).expanduser()
    wanted = set(args.get("skills") or [])
    skills = [s for s in all_skills() if not wanted or s.id in wanted]
    scope = resolve_scope(root, args.get("escopo") or "tudo", args.get("base"))
    with contextlib.redirect_stdout(sys.stderr):  # nada pode sujar o canal do protocolo
        report = run_review(root, skills, scope=scope)
        saved = (report_mod.save(report, root / ".codereview")
                 if args.get("salvar_relatorio", True) else [])
        if saved:
            saved.append(sarif.save_sarif(report, root / ".codereview" / "codereview.sarif"))
    _last[_key(root)] = report
    counts = report.counts()
    score = report.score()
    lines = [
        f"Nota: {score}/100 ({report_mod.grade(score)}) · {len(report.findings)} achados · {report.duration_s}s",
        "Severidades: " + ", ".join(f"{s.label} {counts[s]}" for s in sorted(Severity, reverse=True)),
        "Linguagens: " + (", ".join(f"{k} ({v})" for k, v in report.languages.items()) or "-"),
    ]
    if report.scope:
        lines.append("Escopo: " + report.scope)
    off = [f"{r.skill} ({r.status}: {r.message})" for r in report.results if r.status != "ok"]
    if off:
        lines.append("Skills não executadas: " + "; ".join(off))
    top = sorted(report.findings, key=lambda f: (-f.severity, f.file, f.line))[:TOP_N]
    if top:
        lines += ["", f"Mais graves ({len(top)} de {len(report.findings)}):", *map(_fmt, top)]
    if saved:
        lines += ["", "Relatórios: " + ", ".join(str(p) for p in saved)]
    return "\n".join(lines)


def tool_achados(args: dict) -> str:
    report = _last.get(_key(args["pasta"]))
    if not report:
        raise ValueError("Nenhum code review desta pasta nesta sessão. Rode 'code_review' antes.")
    minimum = Severity.parse(args.get("severidade_minima") or "info")
    items = [f for f in sorted(report.findings, key=lambda f: (-f.severity, f.file, f.line))
             if f.severity >= minimum
             and (not args.get("arquivo") or args["arquivo"].replace("\\", "/").lower() in f.file.lower())
             and (not args.get("skill") or f.skill == args["skill"])]
    limit = min(int(args.get("limite") or 50), MAX_FINDINGS)
    head = f"{len(items)} achado(s)" + (f", mostrando {limit}" if len(items) > limit else "")
    return "\n".join([head, *map(_fmt, items[:limit])])


def tool_listar_skills(_args: dict) -> str:
    return "\n".join(f"- {s.id} [{s.category}]: {s.title} · {s.description}" for s in all_skills())


HANDLERS = {"code_review": tool_code_review, "achados": tool_achados, "listar_skills": tool_listar_skills}


def handle(msg: dict) -> dict | None:
    """Processa uma mensagem JSON-RPC; devolve a resposta, ou None para notificações."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notificação (ex.: notifications/initialized)
        return None
    params = msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        result = {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "codereview-local", "version": __version__},
                  "instructions": ("Code review local e offline. Chame code_review com o caminho absoluto do "
                                   "projeto; use achados para detalhar sem rodar de novo. Depois de corrigir, "
                                   "rode code_review com escopo 'local' ou 'branch' para revisar só o que mudou.")}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name = params.get("name")
        if name not in HANDLERS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Ferramenta desconhecida: {name}"}}
        try:
            text, is_error = HANDLERS[name](params.get("arguments") or {}), False
        except Exception as e:  # o erro volta para a IA em vez de derrubar o servidor
            text, is_error = f"Erro: {type(e).__name__}: {e}", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Método não suportado: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(stdin=None, stdout=None) -> int:
    ensure_std_streams()
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        else:
            reply = handle(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0
