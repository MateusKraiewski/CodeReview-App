# Como contribuir

Obrigado pelo interesse! 🎉 O projeto é aberto para uso e para sugestões, mas **ninguém faz push direto**: toda mudança entra por Pull Request e só o mantenedor ([@MateusKraiewski](https://github.com/MateusKraiewski)) aprova e faz merge na `main`.

## Fluxo

1. Abra uma **issue** descrevendo o bug ou a ideia antes de começar algo grande.
2. Faça um **fork** do repositório e crie uma branch a partir da `main`:
   `git checkout -b feat/minha-skill`
3. Faça as alterações e rode os testes:
   ```bat
   pip install -r requirements.txt pytest
   pytest
   python -m crlocal exemplos\projeto-ruim
   ```
4. Abra um **Pull Request** do seu fork para a `main` deste repositório, preenchendo o template.
5. O CI precisa passar e o mantenedor revisa. Ajustes podem ser pedidos antes do merge.

## Padrões

- Python 3.11+, código e comentários em português, nomes de skills em kebab-case.
- Toda mensagem exibida ao usuário passa por `crlocal/i18n.py` (pt, en, es). Adicione as três traduções.
- Nova skill: veja a seção "Personalizar" do [README](README.md).
- Mantenha a ferramenta **100% offline**: nada de chamadas de rede durante a análise.

## Commits

Mensagens curtas e descritivas, por exemplo `feat: skill de PMD para Java`, `fix: ruff no Windows`, `docs: ...`.
