"""Uso: python -m crlocal <pasta> [--saida pasta] [--skills id1,id2] [--json saida.json]"""
from __future__ import annotations

import argparse
import json
import sys

from . import report as report_mod
from . import sarif
from .i18n import LANGUAGES, set_language, t
from .runner import run_review
from .skills import all_skills


def main(argv=None) -> int:
    if "--mcp" in (argv if argv is not None else sys.argv[1:]):
        from .mcp_server import serve

        return serve()
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", default="pt", choices=list(LANGUAGES))
    set_language(pre.parse_known_args(argv)[0].lang)

    ap = argparse.ArgumentParser(prog="crlocal", description=t("cli.desc"), parents=[pre])
    ap.add_argument("pasta", nargs="?")
    ap.add_argument("--skills", help="ids separados por vírgula (padrão: todas)")
    ap.add_argument("--json", help="salvar achados em JSON")
    ap.add_argument("--saida", help="pasta onde salvar o relatório .md e .pdf")
    ap.add_argument("--sarif", help="salvar os achados em SARIF 2.1.0 (VS Code, Visual Studio, GitHub)")
    ap.add_argument("--problemas", action="store_true",
                    help="imprimir os achados no formato arquivo:linha:coluna (painel Problemas do VS Code)")
    ap.add_argument("--mcp", action="store_true", help="iniciar como servidor MCP (stdio) para IDEs com IA")
    ap.add_argument("--resumo", help="salvar a situação de cada skill em JSON (usado no CI)")
    ap.add_argument("--listar", action="store_true", help="listar skills e sair")
    args = ap.parse_args(argv)

    skills = all_skills()
    if args.listar:
        for s in skills:
            print(f"{s.id:22} {s.title}")
        return 0
    if not args.pasta:
        ap.error(t("cli.folder_required"))
    if args.skills:
        wanted = set(args.skills.split(","))
        skills = [s for s in skills if s.id in wanted]

    report = run_review(args.pasta, skills, progress=lambda title, r: print(
        f"  {'✔' if r and r.status == 'ok' else '•' if r is None else '–'} {title}"
        + (f": {t('cli.found', n=len(r.findings))}" if r and r.status == "ok" else f": {r.message}" if r else ""),
        file=sys.stderr))
    print(f"\n{t('r.languages')}: {report.languages}")
    print(f"{t('r.score')}: {report.score()}/100  |  " + "  ".join(f"{s.label}: {n}" for s, n in sorted(report.counts().items(), reverse=True)))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([f.to_dict() for f in report.findings], fh, ensure_ascii=False, indent=2)
    if args.sarif:
        print(t("cli.report", path=sarif.save_sarif(report, args.sarif)), file=sys.stderr)
    if args.problemas:
        print("\n".join(sarif.problem_lines(report)))
    if args.resumo:
        with open(args.resumo, "w", encoding="utf-8") as fh:
            json.dump({r.skill: {"status": r.status, "achados": len(r.findings), "mensagem": r.message}
                       for r in report.results}, fh, ensure_ascii=False, indent=2)
    if args.saida:
        for path in report_mod.save(report, args.saida):
            print(t("cli.report", path=path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
