# Splunk Alert Response Pipeline

**Bottom line:** este pipeline recebe alertas do Splunk por um webhook,
os persiste e envia uma notificação por e-mail, com a resposta se
ramificando por severidade (urgente ou normal), conduzida pelo próprio
dado do alerta, sem ficar fixa em um único caminho. A entrega do webhook
foi confirmada com um alerta T1110 real; a persistência, a ramificação e
o e-mail foram validados com payloads simulados, e uma execução completa
com um alerta real ainda está pendente.

É uma camada leve de automação: **Trigger >> Enriquecimento >> Decisão >> Ação**,
construída para se conectar ao lab de SOC doméstico
([soc-lab](https://github.com/Kanetahk/soc-lab)) e crescer com o tempo
até virar um pipeline mais amplo de detecção e resposta. De propósito,
ainda não se chama SOAR — orquestração de verdade, cobrindo múltiplos
tipos de alerta e ação remota, ainda está por vir, não é algo que o
escopo atual já mereça.

*Read this in: [English](./README.md)*

## Início rápido

O lab inteiro, em ordem. Cada comando `celery` e `uvicorn` vai no seu próprio terminal, iniciado na raiz do repositório.

**Só na primeira vez**, a partir da raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate
sudo pacman -S valkey    # Celery broker: Valkey (or Redis)
pip install -r requirements.txt
sudo systemctl enable --now valkey
```

Crie um `.env` na raiz do repositório (nunca commitado) com:

```
EMAIL_SENDER=
EMAIL_APP_PASSWORD=
EMAIL_RECIPIENT=
```

**Toda vez**

```bash
# 1. soc-lab/ = Splunk
docker compose up -d

# 2. splunk-alert-response-pipeline/ = worker do Celery
source .venv/bin/activate
cd src
celery -A tasks worker --loglevel=info

# 3. splunk-alert-response-pipeline/ = webhook
source .venv/bin/activate
cd src
uvicorn api:app --host 0.0.0.0 --port 8001
```

Depois, abra o Splunk Web em <http://127.0.0.1:8000> (usuário `admin`, senha `SPLUNK_PASSWORD` do `.env` do soc-lab).

## Construído com

Python 3.14 · FastAPI · Celery · Redis (Valkey) · SQLAlchemy · Pydantic

## Arquitetura

- **Trigger**: endpoint FastAPI (`api.py`) recebendo a ação de alerta
  nativa do tipo Webhook do Splunk, validado como um formato genérico
  `{search_name, result}` (sem suposição sobre campo específico de
  alerta).
- **Enriquecimento**: `indicators.py` mapeia cada tipo de alerta para o
  indicador e a severidade relevantes (ex: `user` + `severity` para
  brute force local, `source_ip` para alertas baseados em rede, quando
  implementados).
- **Decisão**: `actions.py` ramifica a resposta por severidade: alta
  marca a notificação como urgente, média manda como aviso normal,
  decidido a partir de um campo que a busca SPL calcula
  (`eval severity=...`), não fixo por tipo de alerta.
- **Persistência**: todo alerta processado, incluindo sua severidade, é
  armazenado em SQLite via SQLAlchemy (`model.py`).
- **Ação**: atualmente, notificação por e-mail via `smtplib`
  (`notifications.py`), com cabeçalhos de prioridade para alertas de
  severidade alta. Ação remota/de bloqueio está fora do escopo deste
  projeto, nenhuma detecção implementada até agora tem indicador de
  rede para agir em cima.

Tudo isso roda como uma task do Celery, enfileirada via Redis (Valkey no
Arch), então o webhook responde ao Splunk imediatamente, sem esperar o
enriquecimento, a persistência ou a notificação terminarem.

## Estrutura do projeto

```
splunk-alert-response-pipeline/
├── data/
│   └── soar.db             # Banco SQLite (ignorado pelo git)
├── src/
│   ├── api.py            # Endpoint FastAPI do webhook (Trigger)
│   ├── tasks.py           # Task do Celery — orquestra o pipeline inteiro
│   ├── indicators.py      # Mapeia tipo de alerta → indicador + severidade (Enriquecimento)
│   ├── model.py            # Schema SQLAlchemy (Persistência)
│   ├── actions.py          # Mapeia severidade → resposta (Decisão)
│   └── notifications.py    # Envio de e-mail (smtplib)
├── locales/
│   └── pt-br/
│       └── README.md
├── .gitignore
├── README.md
└── requirements.txt
```

## Detecção atual

[T1110 - Brute Force (autenticação via sudo)](https://github.com/Kanetahk/soc-lab/blob/main/detections/T1110-sudo-bruteforce.md),
implementada no repositório irmão [soc-lab](https://github.com/Kanetahk/soc-lab).

## Uso

Simule um alerta do Splunk sem precisar do próprio Splunk rodando:
duas severidades, para ver a ramificação:

```bash
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "3", "severity": "medium"}}'
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "6", "severity": "high"}}'
```

Resultado esperado:
- `{"status": "recebido"}` retornado imediatamente, nos dois
- O log do worker do Celery mostra cada alerta salvo e notificado
- Duas linhas novas aparecem em `data/soar.db`, com `severity` diferente
- Dois e-mails chegam, o de severidade `high` marcado com `[URGENT]` e sinalizado como prioridade alta pelo seu cliente de e-mail

Para o alerta disparando de verdade, a partir de uma instância real do
Splunk, veja o [soc-lab](https://github.com/Kanetahk/soc-lab).

## Limitações conhecidas

- **Sem autenticação no webhook.** O endpoint `/webhook` aceita
  qualquer POST que chegue nele, neste lab ele só está exposto em
  `127.0.0.1`, mas um deploy de produção precisaria de um segredo
  compartilhado ou de verificação de assinatura para confirmar que a
  requisição realmente veio do Splunk.
- **Esta detecção é local, não baseada em rede; ação remota de bloqueio está fora do escopo deste projeto.**
  O `pam_faillock` já bloqueia a conta após falhas repetidas; este
  pipeline oferece *visibilidade* (persistência + notificação), não
  bloqueio, para este alerta.
- **Sem nova tentativa em falha de notificação.** Se o envio por SMTP
  falhar (problema de rede, limite do provedor), a task do Celery falha
  sem nenhuma política de retry configurada.
- **Só um tipo de alerta implementado.** O schema e o padrão
  `indicators.py`/`actions.py`, incluindo a ramificação por severidade,
  foram desenhados para suportar múltiplos tipos de alerta, mas só o
  T1110 os exercita hoje. Um alerta baseado em rede é o próximo passo
  natural para validar que o design generaliza além de um caso só.
- **Escala de laboratório, não de produção.** SQLite, um único worker
  do Celery, Splunk de nó único, suficiente para provar o pipeline, não
  dimensionado para tráfego real.

## Projetos relacionados

- [soc-lab](https://github.com/Kanetahk/soc-lab) - engenharia de detecção no Splunk, onde são construídos os alertas que disparam este pipeline
- [siem-detection-simulator](https://github.com/Kanetahk/siem-detection-simulator) - gerador de logs sintéticos para testar as detecções que alimentam este pipeline (em desenvolvimento)