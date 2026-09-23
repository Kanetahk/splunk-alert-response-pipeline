# Pipeline de Resposta a Alertas do Splunk

**Bottom line:** este pipeline detecta, persiste e notifica sobre
alertas reais do Splunk de ponta a ponta, testado contra alertas
disparando de verdade, não só payload simulado. A resposta se
ramifica por severidade (e-mail marcado com severidade alta ou normal),
decidido a partir do próprio dado do alerta, não fixo num caminho só.

É uma camada leve de automação: **Trigger >> Enriquecimento >> Decisão >> Ação**
construída pra plugar no home SOC lab
([soc-lab](https://github.com/Kanetahk/soc-lab)) e crescer aos poucos
rumo a um pipeline de detecção e resposta mais amplo. Ainda não se
chama SOAR de propósito, orquestração de verdade, cobrindo múltiplos
tipos de alerta e ação remota, ainda está por vir, não é algo que o
escopo atual já mereça.

*Read this in: [English](./README.md)*

## Construído com

Python 3.14 · FastAPI · Celery · Redis (Valkey) · SQLAlchemy · Pydantic

## Arquitetura

- **Trigger** — endpoint FastAPI (`api.py`) recebendo a ação nativa de
  alerta do tipo Webhook do Splunk, validado como um formato genérico
  `{search_name, result}` (sem suposição sobre campo específico de
  alerta).
- **Enriquecimento** — `indicators.py` mapeia cada tipo de alerta pro
  indicador relevante e a severidade (ex: `user` + `severity` pra
  brute-force local, `source_ip` pra alertas baseados em rede, quando
  implementados).
- **Decisão** — `actions.py` ramifica a resposta por severidade: alta
  marca a notificação como crítico, média manda como aviso normal,
  decidido a partir de um campo que o próprio SPL calcula (`eval
  severity=...`), não fixo por tipo de alerta.
- **Persistência** — todo alerta processado, incluindo sua
  severidade, é armazenado em SQLite via SQLAlchemy (`model.py`).
- **Ação** — atualmente, notificação por e-mail via `smtplib`
  (`notifications.py`), com cabeçalho de prioridade marcado pra
  alerta de severidade alta. Ação remota/de bloqueio está fora do
  escopo desse projeto, nenhuma detecção implementada até agora tem
  indicador de rede pra agir em cima.

Tudo isso roda como uma task do Celery, enfileirada via Redis (Valkey
no Arch), então o webhook responde ao Splunk imediatamente, sem
esperar enriquecimento, persistência ou notificação terminarem.

## Estrutura do projeto

```
├── src/
│   ├── api.py            # Endpoint FastAPI do webhook (Trigger)
│   ├── tasks.py           # Task do Celery — orquestra o pipeline inteiro
│   ├── indicators.py      # Mapeia tipo de alerta → indicador + severidade (Enriquecimento)
│   ├── model.py            # Schema SQLAlchemy (Persistência)
│   ├── actions.py          # Mapeia severidade → resposta (Decisão)
│   └── notifications.py    # Envio de e-mail (smtplib)
├── data/
│   └── soar.db             # Banco SQLite (ignorado pelo git)
└── requirements.txt
```

## Detecção atual

[T1110 - Brute Force (autenticação via sudo)](https://github.com/Kanetahk/soc-lab/blob/main/detections/T1110-sudo-bruteforce.md),
implementada no repositório irmão [soc-lab](https://github.com/Kanetahk/soc-lab).

## Configuração

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requer Redis ou Valkey instalado e rodando (ex: `sudo pacman -S valkey && sudo systemctl enable --now valkey` no Arch).

Variáveis de ambiente necessárias (`.env`, nunca commitado):
```
GITHUB_TOKEN=
EMAIL_SENDER=
EMAIL_APP_PASSWORD=
EMAIL_RECIPIENT=
```

## Uso

De dentro de `src/`, sobe os dois processos:

```bash
cd src
celery -A tasks worker --loglevel=info
```
```bash
cd src
uvicorn api:app --host 0.0.0.0 --port 8001
```

Simula um alerta do Splunk sem precisar do Splunk rodando:
duas severidades, pra ver a ramificação:

```bash
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "3", "severity": "medium"}}'
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "6", "severity": "high"}}'
```

Resultado esperado:
- `{"status": "recebido"}` retornado imediatamente, nos dois
- Log do worker Celery mostra cada alerta salvo e notificado
- Duas linhas novas aparecem em `data/soar.db`, com `severity`
  diferente
- Dois e-mails chegam, o de severidade `high` marcado `[URGENT]` e
  sinalizado como prioridade alta pelo seu cliente de e-mail

Pro alerta disparando de verdade, a partir de uma instância real do
Splunk, veja [soc-lab](https://github.com/Kanetahk/soc-lab).

## Limitações conhecidas

- **Sem autenticação no webhook.** O endpoint `/webhook` aceita
  qualquer `POST` que chegue nele, nesse lab, só está exposto pra
  `127.0.0.1`, mas um deploy de produção precisaria de um segredo
  compartilhado ou verificação de assinatura pra confirmar que a
  requisição realmente veio do Splunk.
- **Essa detecção é local, não baseada em rede; ação remota de bloqueio está fora do escopo desse projeto.**
  O `pam_faillock` já
  bloqueia a conta localmente após tentativas repetidas; esse
  pipeline oferece *visibilidade* (persistência + notificação), não
  bloqueio, pra esse alerta.
- **Sem nova tentativa em falha de notificação.** Se o envio via SMTP
  falhar (problema de rede, limite do provedor), a task do Celery
  falha sem nenhuma política de retry configurada.
- **Só um tipo de alerta implementado.** O schema e o padrão
  `indicators.py`/`actions.py`, incluindo a ramificação por
  severidade, foram desenhados pra suportar múltiplos tipos de
  alerta, mas só o T1110 exercita eles hoje. Um alerta baseado em rede
  é o próximo passo natural pra validar se o design generaliza além
  de um caso só.
- **Escala de laboratório, não de produção.** SQLite, um único worker
  Celery, Splunk de nó único, suficiente pra provar o pipeline, não
  dimensionado pra tráfego real.