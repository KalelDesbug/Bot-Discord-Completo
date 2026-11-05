# Discord Community Bot/FEITO COM IA

Bot de comunidade em Python com tickets, boas-vindas configuráveis, moderação com confirmação e comandos úteis/divertidos.

## Requisitos

- Python 3.10+
- Aplicação criada no [Discord Developer Portal](https://discord.com/developers/applications)
- `Server Members Intent` habilitado no portal para o evento de boas-vindas

Copie `.env.example` para `.env` e preencha `DISCORD_TOKEN`.

## Configuração fácil do bot

Edite `config-bot.json` na pasta principal do projeto. As opções foram pensadas para poderem ser alteradas sem mexer no código:

- `restart.enabled`: `true` para reiniciar automaticamente ou `false` para desativar o reinício programado.
- `restart.interval_hours`: intervalo em horas, de 1 a 720. Exemplo: `24` significa uma vez por dia.
- `restart.retry_seconds`: espera antes de tentar iniciar o bot novamente após uma desconexão ou encerramento inesperado.
- `logs.discord_enabled`: `true` envia logs ao canal configurado no Discord; `false` desativa apenas o envio ao Discord.
- `logs.console_level`: nível de detalhes no console: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`.

Exemplo: para desligar o reinício programado, mude `"enabled": true` para `"enabled": false`. Para reiniciar a cada 12 horas, use `"interval_hours": 12`. Salve o arquivo e reinicie o processo do bot para aplicar as alterações.

O arquivo é JSON: mantenha aspas duplas e vírgulas entre os campos. Se ele estiver ausente, o bot usa os padrões (reinício ligado a cada 24 horas e logs habilitados). Valores inválidos mostram uma mensagem de configuração clara em vez de iniciar com comportamento inesperado.

## Configuração no servidor

Convide o bot com os escopos `bot` e `applications.commands`. Conceda somente as permissões necessárias: ver canais, enviar mensagens, gerenciar canais (tickets), banir membros, expulsar membros e moderar membros.

1. `/configurar_boas_vindas` define o canal e a mensagem. Placeholders: `{member}` e `{server}`.
2. `/configurar_tickets` escolhe a categoria e o cargo de suporte.
3. `/publicar_painel_tickets` publica o botão de abertura de tickets no canal atual.
4. `/configurar_logs` configura o canal de logs.

Comandos de moderação: `/ban`, `/kick` e `/timeout`. Todos exigem confirmação e checam permissões e hierarquia. Outros comandos: `/ping`, `/avatar`, `/userinfo`, `/moeda` e `/bola8`.
