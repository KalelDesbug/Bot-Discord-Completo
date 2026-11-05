# Discord Community Bot/FEITO COM IA

Bot de comunidade em Python com tickets, boas-vindas configuráveis, moderação com confirmação e comandos úteis/divertidos.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.6%2B-5865F2?style=flat-square&logo=discord&logoColor=white)
![SQLite](https://img.shields.io/badge/Banco-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-green?style=flat-square)

</div>

---

## Funcionalidades

- **Tickets:** sistema de atendimento privado com painel de abertura e botão para fechar.
- **Boas-vindas:** mensagens personalizáveis para novos membros.
- **Moderação:** comandos para banir, expulsar e aplicar timeout, todos com confirmação.
- **Logs:** registro de eventos e erros, com opções de configuração.
- **Comandos úteis:** ping, avatar, informações de usuários e outros.
- **Comandos divertidos:** moeda e bola 8.
- **Reinicialização automática:** intervalo e tentativas de reconexão configuráveis.

## Requisitos

- Python 3.10+
- Aplicação criada no [Discord Developer Portal](https://discord.com/developers/applications)
- `Server Members Intent` habilitado no portal para o evento de boas-vindas.

## Instalação

Clone o repositório:

```bash
git clone <URL_DO_REPOSITORIO>
cd <PASTA_DO_PROJETO>
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `DISCORD_TOKEN` com o token do seu bot.

Para iniciar:

```bash
python -m src.bot_app
```

## Configuração no servidor

Convide o bot com os escopos `bot` e `applications.commands`.

Conceda somente as permissões necessárias: visualizar canais, enviar mensagens, gerenciar canais (tickets), banir membros, expulsar membros e moderar membros.

### Comandos de configuração

1. `/configurar_boas_vindas` — define o canal e a mensagem de boas-vindas. Placeholders disponíveis: `{member}` e `{server}`.
2. `/configurar_tickets` — configura a categoria e o cargo de suporte.
3. `/publicar_painel_tickets` — publica o botão de abertura de tickets no canal atual.
4. `/configurar_logs` — configura o sistema de registros do bot.

### Comandos de moderação

| Comando | Descrição |
|---|---|
| `/ban` | Bane um membro do servidor. |
| `/kick` | Expulsa um membro do servidor. |
| `/timeout` | Aplica um tempo limite a um membro. |

Todos exigem confirmação e verificam permissões e hierarquia antes da execução.

### Outros comandos

| Comando | Descrição |
|---|---|
| `/ping` | Exibe a latência do bot. |
| `/avatar` | Exibe o avatar de um usuário. |
| `/userinfo` | Mostra informações de um usuário. |
| `/moeda` | Simula um lançamento de moeda. |
| `/bola8` | Responde perguntas aleatórias. |

## Configurações adicionais

O arquivo `config-bot.json` permite ajustar opções gerais sem precisar alterar o código-fonte.

Entre as opções disponíveis estão:

- Ativação da reinicialização automática.
- Intervalo entre reinicializações.
- Tempo de espera para novas tentativas de conexão.
- Ativação dos logs no Discord.
- Nível de log do console (`INFO`, `DEBUG` e outros).

## Problemas e contribuições

Encontrou algum problema ou tem uma sugestão?

Abra uma [Issue](../../issues) descrevendo o erro ou a melhoria que gostaria de propor.

Contribuições também são bem-vindas.

## Licença

Este projeto está distribuído sob a licença [MIT](LICENSE). Consulte o arquivo para conhecer os termos de uso, modificação e distribuição.
