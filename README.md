<div align="center">

# 🤖 Bot Discord Completo

**Bot de comunidade com tickets, boas-vindas, moderação e comandos úteis.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.6%2B-5865F2?style=flat-square&logo=discord&logoColor=white)
![SQLite](https://img.shields.io/badge/Banco-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-green?style=flat-square)

</div>

---

## ✨ Recursos

- 🎫 Tickets privados com painel e botão para fechar
- 👋 Boas-vindas configuráveis por servidor
- 🛡️ Moderação com confirmação: ban, kick e timeout
- 📋 Logs configuráveis e coloridos
- 🎲 Comandos: `/ping`, `/avatar`, `/userinfo`, `/moeda` e `/bola8`
- 🔄 Reinício automático configurável

## 🚀 Começar

Requer Python 3.10+ e uma aplicação criada no [Discord Developer Portal](https://discord.com/developers/applications). Ative o **Server Members Intent** para as boas-vindas.

```bash
pip install -r requirements.txt
```

Crie `.env` a partir de `.env.example`, preencha `DISCORD_TOKEN` e inicie:

```bash
python -m src.bot_app
```

## ⚙️ Configuração

Edite `config-bot.json` para ajustar opções sem alterar o código:

- `restart.enabled`: `true` ou `false`
- `restart.interval_hours`: intervalo entre reinícios, de 1 a 720 horas
- `restart.retry_seconds`: espera antes de tentar reconectar
- `logs.discord_enabled`: ativa ou desativa logs no Discord
- `logs.console_level`: nível de log, como `INFO` ou `DEBUG`

No servidor, configure as boas-vindas com `/configurar_boas_vindas`, os tickets com `/configurar_tickets` e `/publicar_painel_tickets`, e os logs com `/configurar_logs`. Convide o bot com os escopos `bot` e `applications.commands`, concedendo apenas as permissões necessárias.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
