# CodeReview Local

[![CI](https://github.com/MateusKraiewski/CodeReview-App/actions/workflows/ci.yml/badge.svg)](https://github.com/MateusKraiewski/CodeReview-App/actions/workflows/ci.yml) [![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green.svg)](LICENSE) ![Windows](https://img.shields.io/badge/Windows-10%2F11-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![Offline](https://img.shields.io/badge/100%25-offline-brightgreen)

**Code review 100% offline, sem IA e sem tokens.** Você escolhe a pasta de um projeto, a ferramenta roda várias "skills" de análise (ferramentas open source consagradas + regras próprias) e gera um relatório em **PDF** e **Markdown** com nota, prioridades e sugestões de correção.

> 🇺🇸 [English](#english) · 🇪🇸 [Español](#español)

![Tela do app](docs/tela.png)

## Recursos

- **App desktop para Windows**: campo de busca da pasta com histórico de projetos recentes, seleção de skills, lista de achados com filtro por severidade e detalhes com sugestão.
- **Relatório em PDF e Markdown**: nota de 0 a 100 com conceito (A–E), resumo por severidade, skills executadas, top 10 prioridades e achados agrupados por arquivo. Veja o [exemplo em PDF](docs/relatorio-exemplo.pdf) ou [em Markdown](docs/relatorio-exemplo.md).
- **3 idiomas**: português, inglês e espanhol, tanto na tela quanto no relatório.
- **Offline de verdade**: nada sai da sua máquina. A internet só é usada uma vez, para baixar as ferramentas e as bases de regras e vulnerabilidades.
- **Tolerante a falhas**: se uma ferramenta não estiver instalada, a skill é marcada como "Pulada" no relatório e as outras continuam.
- **Sem achados duplicados**: quando duas ferramentas apontam o mesmo problema na mesma linha (ex.: SQL injection no Semgrep e no Bandit), ele aparece uma vez só.

## Skills de CR

| id | Skill | Ferramenta | Linguagens |
|---|---|---|---|
| `segredos` | Segredos no código (senhas, tokens, chaves) | [Gitleaks](https://github.com/gitleaks/gitleaks) | todas |
| `seguranca-sast` | Segurança: SQL injection, XSS, crypto fraca, desserialização | [Semgrep CE](https://github.com/semgrep/semgrep) + regras offline | 30+ |
| `seguranca-devskim` | Padrões inseguros | [Microsoft DevSkim](https://github.com/microsoft/DevSkim) | C#, JS, Python, Java, C/C++… |
| `seguranca-python` | Segurança Python | [Bandit](https://github.com/PyCQA/bandit) | Python |
| `dependencias` | Pacotes com CVE conhecida (NuGet, npm, PyPI, Maven…) | [OSV-Scanner](https://github.com/google/osv-scanner) | todas |
| `qualidade-csharp` | Regras oficiais CAxxxx/IDExxxx | Roslyn Analyzers (`dotnet build`) | C# |
| `qualidade-python` | Bugs prováveis, código morto, PEP 8 | [Ruff](https://github.com/astral-sh/ruff) | Python |
| `complexidade` | Complexidade ciclomática, métodos longos, muitos parâmetros | [Lizard](https://github.com/terryyin/lizard) | 20+ |
| `duplicacao` | Código copiado e colado | Lizard | 20+ |
| `testes` | Projeto sem testes / arquivos sem teste correspondente | regra própria | todas |
| `padroes` | Nomenclatura e padrões do time (async void, catch vazio, `throw ex`, `.Result`, console.log, TODO…) | regras YAML próprias | C#, Python, JS/TS |

A pesquisa que levou a essa seleção (popularidade, licença, suporte a Windows) está em [docs/pesquisa-skills.md](docs/pesquisa-skills.md).

## Instalação (Windows)

Pré-requisitos: **Python 3.11+** e, para a skill de C#, o **.NET SDK**.

```bat
git clone https://github.com/MateusKraiewski/CodeReview-App.git
cd CodeReview-App
build.bat
```

O `build.bat` (rode uma vez, com internet):

1. cria um ambiente virtual e instala as dependências Python;
2. baixa `gitleaks.exe`, `osv-scanner.exe`, `ruff.exe` e o DevSkim para a pasta `tools\` ([scripts/baixar_ferramentas.ps1](scripts/baixar_ferramentas.ps1));
3. baixa as regras públicas do Semgrep para `rules\` ([scripts/baixar_regras.py](scripts/baixar_regras.py));
4. gera o app em `dist\CodeReviewLocal\CodeReviewLocal.exe` com PyInstaller.

Depois disso, copie a pasta `dist\CodeReviewLocal` para onde quiser. Ela funciona sem internet.

### Rodar sem gerar o .exe

```bat
pip install -r requirements.txt
pythonw CodeReviewLocal.pyw
```

## Uso

**App desktop**

1. Escolha o idioma no canto superior direito.
2. Digite ou cole o caminho da pasta do projeto, ou clique em **Procurar…**. Os projetos recentes ficam na lista.
3. Marque as skills (passe o mouse para ver a descrição) e os formatos do relatório.
4. Clique em **Analisar**. Ao terminar, use **Abrir PDF**, **Abrir Markdown** ou **Abrir pasta**.

Os relatórios são salvos em `Documentos\CodeReviewLocal` (configurável na tela) com o nome `CR_<projeto>_<data>.pdf/.md`.

**Linha de comando**

```bat
python -m crlocal C:\projetos\MinhaApi --saida C:\relatorios --lang pt
python -m crlocal C:\projetos\MinhaApi --skills segredos,qualidade-csharp,padroes --json achados.json
python -m crlocal --listar
```

| Opção | Descrição |
|---|---|
| `--saida PASTA` | salva o relatório `.md` e `.pdf` |
| `--lang pt\|en\|es` | idioma das mensagens e do relatório |
| `--skills a,b,c` | roda só as skills indicadas |
| `--json ARQ` | exporta os achados em JSON (útil para CI) |

## Como a nota é calculada

Cada achado tem um peso: Crítica 10, Alta 5, Média 2, Baixa 0,5 e Info 0. A soma é normalizada pelo tamanho do projeto (quantidade de arquivos):

`nota = 100 / (1 + penalidade / (10 + 2 × arquivos))`

| Nota | Conceito |
|---|---|
| 90–100 | A (excelente) |
| 75–89 | B (bom) |
| 60–74 | C (atenção) |
| 40–59 | D (ruim) |
| 0–39 | E (crítico) |

## Personalizar

**Regras do time**: edite [crlocal/rules/padroes.yaml](crlocal/rules/padroes.yaml). Cada regra é uma regex com severidade, mensagem e sugestão, que podem ser escritas nos 3 idiomas:

```yaml
- id: cs-catch-vazio
  languages: [C#]
  pattern: 'catch\s*(\([^)]*\))?\s*\{\s*\}'
  severity: alta            # critica | alta | media | baixa | info
  exclude_paths: 'Tests?'   # opcional
  message:
    pt: "Bloco catch vazio engole exceções."
    en: "Empty catch block swallows exceptions."
    es: "Bloque catch vacío que se traga las excepciones."
  suggestion: "Registre o erro (ILogger) ou relance com 'throw;'."
```

**Regras de segurança próprias**: coloque arquivos Semgrep `.yaml` em [crlocal/rules/semgrep/](crlocal/rules/semgrep/). Use `metadata.message_en` / `message_es` para traduzir.

**Nova skill**: crie uma classe em `crlocal/skills/` herdando `Skill`, implemente `analyze(root, languages)` retornando `list[Finding]`, registre em `crlocal/skills/__init__.py` e adicione o título e a descrição em `crlocal/i18n.py` (`skill.<id>.title` / `skill.<id>.desc`).

**Novo idioma**: adicione o código em `LANGUAGES` e uma coluna nas tuplas de `crlocal/i18n.py`.

## Estrutura

```
crlocal/
  gui.py            app desktop (Tkinter)
  __main__.py       linha de comando
  runner.py         executa as skills em paralelo
  report.py         relatório Markdown e PDF (ReportLab)
  i18n.py           traduções pt / en / es
  dedupe.py         une achados repetidos entre ferramentas
  detect.py         detecta linguagens e ignora bin/obj/node_modules/.git…
  tools.py          localiza executáveis (tools\ embutido → PATH)
  models.py         Finding, Severity, Report, cálculo da nota
  skills/           um arquivo por skill
  rules/            padroes.yaml e regras Semgrep próprias
build/              spec do PyInstaller e ponto de entrada do .exe
scripts/            download das ferramentas e regras
docs/               captura de tela, relatório de exemplo e pesquisa
exemplos/           projeto com problemas propositais para testar
tests/              testes automatizados (pytest)
.github/            CI, templates de issue/PR e CODEOWNERS
```

## Limitações conhecidas

- As mensagens das ferramentas externas (Bandit, Ruff, Semgrep, Roslyn, OSV) aparecem no idioma original, normalmente em inglês. As skills próprias e o relatório seguem o idioma escolhido.
- A skill de C# compila o projeto. Os pacotes NuGet precisam estar no cache local, o que é o normal se o projeto já compilou na sua máquina.
- O suporte do Semgrep no Windows ainda é beta. Se ele falhar, o DevSkim continua cobrindo segurança.
- A base do OSV-Scanner é baixada na primeira execução. Depois disso funciona offline.

## Contribuindo

O projeto é aberto: qualquer pessoa pode baixar, usar e sugerir melhorias. Ninguém faz push direto na `main`. Toda mudança chega por **Pull Request a partir de um fork**, passa pelo CI e precisa da aprovação do mantenedor. Veja o [CONTRIBUTING.md](CONTRIBUTING.md). Vulnerabilidades: [SECURITY.md](SECURITY.md).

## Licenças

Código sob licença [MIT](LICENSE). Ferramentas usadas: Gitleaks (MIT), Semgrep CE (LGPL-2.1, regras sob Semgrep Rules License: uso interno permitido), DevSkim (MIT), Bandit (Apache-2.0), OSV-Scanner (Apache-2.0), Ruff (MIT), Lizard (MIT), ReportLab (BSD).

---

## English

**100% offline code review, no AI, no tokens.** Pick a project folder and the app runs several analysis skills (well-known open-source tools plus custom rules). It then produces a **PDF** and **Markdown** report with a 0–100 score, priorities and fix suggestions. The UI and the report are available in **Portuguese, English and Spanish**: pick the language in the top-right corner, or use `--lang en` on the command line.

- Install: `build.bat` (needs Python 3.11+; the .NET SDK is needed for the C# skill). It downloads the tools once and builds `dist\CodeReviewLocal\CodeReviewLocal.exe`.
- Run without building: `pip install -r requirements.txt` then `pythonw CodeReviewLocal.pyw`.
- CLI: `python -m crlocal <folder> --saida <out-dir> --lang en`.
- Team rules: `crlocal/rules/padroes.yaml`.
- Contributing: fork + Pull Request only; the maintainer reviews and merges. See [CONTRIBUTING.md](CONTRIBUTING.md). License: MIT.

## Español

**Code review 100% offline, sin IA y sin tokens.** Elija la carpeta de un proyecto y la aplicación ejecuta varias skills de análisis (herramientas open source reconocidas y reglas propias). Luego genera un informe en **PDF** y **Markdown** con nota de 0 a 100, prioridades y sugerencias. La interfaz y el informe están en **portugués, inglés y español**: elija el idioma arriba a la derecha, o use `--lang es` en la línea de comandos.

- Instalación: `build.bat` (requiere Python 3.11+; el .NET SDK hace falta para la skill de C#).
- Ejecutar sin compilar: `pip install -r requirements.txt` y `pythonw CodeReviewLocal.pyw`.
- CLI: `python -m crlocal <carpeta> --saida <salida> --lang es`.
- Reglas del equipo: `crlocal/rules/padroes.yaml`.
- Contribuir: solo con fork + Pull Request; el mantenedor revisa y hace el merge. Ver [CONTRIBUTING.md](CONTRIBUTING.md). Licencia: MIT.
