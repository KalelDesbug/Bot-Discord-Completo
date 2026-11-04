# Discord Community Bot

Bot de comunidade em Python com tickets, boas-vindas configuráveis, moderação com confirmação e comandos úteis/divertidos.

## Requisitos

- Python 3.10+
- Aplicação criada no [Discord Developer Portal](https://discord.com/developers/applications)
- `Server Members Intent` habilitado no portal para o evento de boas-vindas

## Instalação

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `DISCORD_TOKEN`. Nunca publique seu token. Inicie o bot na raiz do repositório:

```bash
python -m src.bot_app
```

Se `TEST_GUILD_ID` estiver preenchido, os comandos serão sincronizados apenas nessa guild (útil durante o desenvolvimento). Sem essa variável, serão sincronizados globalmente.

## Configuração no servidor

Convide o bot com os escopos `bot` e `applications.commands`. Conceda somente as permissões necessárias: ver canais, enviar mensagens, gerenciar canais (tickets), banir membros, expulsar membros e moderar membros.

1. `/configurar_boas_vindas` define o canal e a mensagem. Placeholders: `{member}` e `{server}`.
2. `/configurar_tickets` escolhe a categoria e o cargo de suporte.
3. `/publicar_painel_tickets` publica o botão de abertura de tickets no canal atual.

Comandos de moderação: `/ban`, `/kick` e `/timeout`. Todos exigem confirmação e checam permissões e hierarquia. Outros comandos: `/ping`, `/avatar`, `/userinfo`, `/moeda` e `/bola8`.

## Estrutura

```text
src/bot_app/
├── __main__.py
├── bot.py
├── config.py
├── core/
│   └── database.py
└── features/
    ├── moderation/
    ├── tickets/
    ├── utility/
    └── welcome/
```

Os componentes visuais ficam junto da funcionalidade correspondente; não há pasta `Views`. SQL e regras ficam separados dos Cogs para facilitar manutenção e testes.
