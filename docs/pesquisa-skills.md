# Passo 1: Skills de Code Review (pesquisa)

Critérios: popularidade no GitHub, manutenção ativa, licença permissiva, **roda 100% offline** e **roda nativo no Windows**.

> Obs.: as estrelas são aproximadas (ordem de grandeza, 2026). Esta sessão não tem acesso à API do GitHub para buscar o número exato.

## Ferramentas por skill

| Skill | Ferramenta | Estrelas (aprox.) | Licença | Linguagens | Windows | Runtime | MVP? |
|---|---|---|---|---|---|---|---|
| Segredos no código | **Gitleaks** | ~20k | MIT | Todas | Sim, .exe nativo | nenhum | ✅ |
| Segredos (alt.) | detect-secrets (Yelp) | ~4k | Apache-2.0 | Todas | Sim | Python | reserva |
| Segredos (alt.) | TruffleHog | ~20k | AGPL-3.0 ⚠️ | Todas | Sim | nenhum | ❌ licença |
| Segurança (SAST) multi-linguagem | **Semgrep CE** | ~12k | LGPL-2.1 (regras: Semgrep Rules License) | 30+ | Beta nativo ⚠️ | Python | ✅ com fallback |
| Segurança (SAST) multi-linguagem | **DevSkim** (Microsoft) | ~1k | MIT | C#, JS, Python, Java, C/C++ e outras | Sim, nativo | .NET embutido | ✅ |
| Segurança Python | **Bandit** (PyCQA) | ~7k | Apache-2.0 | Python | Sim | Python | ✅ |
| Segurança JS/TS | eslint-plugin-security | ~2k | Apache-2.0 | JS/TS | Sim | Node | Fase 2 |
| Dependências vulneráveis | **OSV-Scanner** (Google) | ~7k | Apache-2.0 | npm, PyPI, Maven, NuGet, Go e outros | Sim, .exe | nenhum | ✅ (base offline baixada antes) |
| Dependências (alt.) | Trivy | ~25k | Apache-2.0 | Muitas | Sim | nenhum | reserva |
| Qualidade e estilo Python | **Ruff** | ~40k | MIT | Python | Sim, .exe | nenhum | ✅ |
| Qualidade e estilo JS/TS | ESLint | ~26k | MIT | JS/TS | Sim | Node | Fase 2 |
| Qualidade Java | PMD | ~5k | BSD-style | Java, Apex, Kotlin, XML | Sim | Java | Fase 2 |
| Qualidade C# | **Roslyn Analyzers** (`dotnet build` + SARIF) | ~1.6k | MIT | C# | Sim | .NET SDK do usuário | ✅ (pula se não houver SDK) |
| Qualidade Go | golangci-lint | ~16k | GPL-3.0 (só executado, sem embutir no código) | Go | Sim | nenhum | Fase 2 |
| Complexidade ciclomática | **Lizard** | ~2k | MIT | 20+ linguagens | Sim | Python | ✅ |
| Código duplicado | **Lizard (-Eduplicate)** | (mesma) | MIT | 20+ | Sim | Python | ✅ |
| Código duplicado (alt.) | jscpd | ~5k | MIT | 150+ formatos | Sim | Node | Fase 2 |
| Testes faltando | **Regra própria** | n/a | nossa | Todas | Sim | Python | ✅ |
| Nomenclatura e padrões do time | **Regras próprias (YAML)** + regras customizadas do Semgrep | n/a | nossa | Todas | Sim | Python | ✅ |

## Proposta para o MVP

Tudo (exceto a skill de C#, que usa o .NET SDK do usuário) roda com **Python embutido e binários .exe**, sem exigir Node, Java ou .NET SDK na máquina:

1. **Gitleaks**: segredos (senhas, tokens, chaves de API).
2. **Semgrep CE** com pacotes de regras baixados e congelados dentro do app. Se ele falhar no Windows, a skill usa **DevSkim** automaticamente.
3. **Bandit**: segurança específica de Python.
4. **OSV-Scanner**: dependências com vulnerabilidades conhecidas. A base de vulnerabilidades é baixada uma vez e depois funciona offline, com um botão "Atualizar base".
5. **Ruff**: qualidade e estilo de Python.
6. **Lizard**: complexidade, funções longas, muitos parâmetros e código duplicado, em mais de 20 linguagens.
7. **Testes faltando** (própria): proporção de arquivos de teste e módulos sem teste correspondente.
8. **Roslyn Analyzers (C#)**: roda `dotnet build` com `AnalysisMode=All` e lê o SARIF. Exige o .NET SDK instalado e é pulado com aviso se ele não existir.
9. **Nomenclatura e padrões** (própria): regras configuráveis em YAML (nomes, TODO/FIXME, `print`/`console.log` esquecidos, arquivos grandes etc.).

**Fase 2 (pacotes opcionais):** ESLint e eslint-plugin-security (JS/TS), PMD (Java), golangci-lint (Go) e jscpd. Cada um vira um "pack" que só ativa se o runtime necessário estiver instalado.

## Riscos e pontos de atenção

- **Semgrep no Windows:** o suporte nativo ainda é beta, então o DevSkim fica como fallback.
- **Licença das regras do Semgrep:** permite uso interno e pessoal. Não pode ser revendida como produto concorrente.
- **TruffleHog** fica de fora por ser AGPL.
- **Instalador:** o tamanho estimado fica entre 150 e 250 MB por causa dos binários embutidos.
