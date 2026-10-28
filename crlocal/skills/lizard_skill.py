from __future__ import annotations

import lizard
from lizard_ext.lizardduplicate import LizardExtension as DuplicateExtension

from ..detect import iter_source_files, rel
from ..i18n import t
from ..models import Severity
from .base import Skill

# Limites inspirados no Sonar/Code Climate
CCN_MEDIA, CCN_ALTA = 10, 20
NLOC_MEDIA, NLOC_ALTA = 60, 120
PARAMS_MEDIA = 6
MIN_DUPLICATE_TOKENS = 100

LIZARD_LANGS = {"Python", "C#", "JavaScript", "TypeScript", "Java", "Kotlin", "Go", "Ruby",
                "PHP", "C", "C++", "Swift", "Rust", "Scala"}


def _analyze_files(root, extensions):
    files = [str(p) for p in iter_source_files(root)]
    return list(lizard.analyze_files(files, exts=lizard.get_extensions(extensions)))


class ComplexitySkill(Skill):
    id = "complexidade"
    category = "Manutenibilidade"
    languages = LIZARD_LANGS

    def analyze(self, root, languages):
        findings = []
        for info in _analyze_files(root, []):
            path = rel(info.filename, root)
            for fn in info.function_list:
                ccn, nloc, params = fn.cyclomatic_complexity, fn.nloc, len(fn.parameters)
                if ccn > CCN_MEDIA:
                    findings.append(self.finding(
                        rule_id="complexidade-ciclomatica",
                        message=t("f.ccn", name=fn.name, value=ccn, limit=CCN_MEDIA),
                        severity=Severity.ALTA if ccn > CCN_ALTA else Severity.MEDIA,
                        file=path, line=fn.start_line,
                        suggestion=t("f.ccn.sug"),
                    ))
                if nloc > NLOC_MEDIA:
                    findings.append(self.finding(
                        rule_id="metodo-longo",
                        message=t("f.long", name=fn.name, value=nloc, limit=NLOC_MEDIA),
                        severity=Severity.MEDIA if nloc > NLOC_ALTA else Severity.BAIXA,
                        file=path, line=fn.start_line,
                        suggestion=t("f.long.sug"),
                    ))
                if params > PARAMS_MEDIA:
                    findings.append(self.finding(
                        rule_id="muitos-parametros",
                        message=t("f.params", name=fn.name, value=params, limit=PARAMS_MEDIA),
                        severity=Severity.BAIXA, file=path, line=fn.start_line,
                        suggestion=t("f.params.sug"),
                    ))
        return findings


class DuplicationSkill(Skill):
    id = "duplicacao"
    category = "Manutenibilidade"
    languages = LIZARD_LANGS

    def analyze(self, root, languages):
        ext = DuplicateExtension()
        files = [str(p) for p in iter_source_files(root)]
        list(lizard.analyze_files(files, exts=lizard.get_extensions([ext])))
        findings = []
        for snippets in ext.get_duplicates(MIN_DUPLICATE_TOKENS):
            snippets = list(snippets)
            first, others = snippets[0], snippets[1:]
            where = ", ".join(f"{rel(s.file_name, root)}:{s.start_line}-{s.end_line}" for s in others)
            size = first.end_line - first.start_line + 1
            findings.append(self.finding(
                rule_id="bloco-duplicado",
                message=t("f.dup", size=size, where=where),
                severity=Severity.MEDIA if size >= 30 else Severity.BAIXA,
                file=rel(first.file_name, root), line=first.start_line,
                suggestion=t("f.dup.sug"),
            ))
        return findings
