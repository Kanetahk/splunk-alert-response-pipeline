# Splunk Alert Response Pipeline

**Bottom line:** this pipeline receives Splunk alerts through a
webhook, persists them, and sends an email notification, with the
response branching by severity (urgent or normal), driven by the alert
data itself rather than hardcoded to a single path. The webhook
delivery was confirmed with a real T1110 alert; persistence, branching
and email were validated with simulated payloads, and a full run with
a real alert is still pending.

It's a lightweight automation layer: **Trigger >> Enrichment >> Decision >> Action**,
built to plug into the home SOC lab
([soc-lab](https://github.com/Kanetahk/soc-lab)) and grow over time
into a broader detection-and-response pipeline. It's intentionally not
called a SOAR yet — real orchestration across multiple alert types and
remote action is still ahead, not something the current scope has
earned.

*Read this in: [Português](./locales/pt-br/README.md)*

## Quick start

The whole lab, in order. Each `celery` and `uvicorn` command goes in its own terminal, started from the repo root.

**First time only**, from the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo pacman -S valkey    # Celery broker: Valkey (or Redis)
sudo systemctl enable --now valkey
```

Create a `.env` in the repo root (never committed) with:

```
EMAIL_SENDER=
EMAIL_APP_PASSWORD=
EMAIL_RECIPIENT=
```

**Every time**

```bash
# 1. soc-lab/ = Splunk
docker compose up -d

# 2. splunk-alert-response-pipeline/ = Celery worker
source .venv/bin/activate
cd src
celery -A tasks worker --loglevel=info

# 3. splunk-alert-response-pipeline/ = webhook
source .venv/bin/activate
cd src
uvicorn api:app --host 0.0.0.0 --port 8001
```

Then open Splunk Web at <http://127.0.0.1:8000> (user `admin`, password is `SPLUNK_PASSWORD` from the soc-lab `.env`).

## Built with

Python 3.14 · FastAPI · Celery · Redis (Valkey) · SQLAlchemy · Pydantic

## Architecture

- **Trigger** FastAPI endpoint (`api.py`) receiving Splunk's native
  Webhook alert action, validated as a generic `{search_name, result}`
  shape (no assumption about specific alert fields).
- **Enrichment** `indicators.py` maps each alert type to its relevant
  indicator and severity (e.g. `user` + `severity` for local brute-force,
  `source_ip` for network-based alerts once implemented).
- **Decision** `actions.py` branches the response by severity: high
  marks the notification urgent, medium sends it as a normal notice,
  decided from a field the SPL search computes (`eval severity=...`),
  not hardcoded per alert type.
- **Persistence** every processed alert, including its severity,
  is stored in SQLite via SQLAlchemy (`model.py`).
- **Action** currently email notification via `smtplib`
  (`notifications.py`), with priority headers set for high-severity alerts.
  Remote/blocking action is out of scope for this project, no detection
  implemented so far has a network indicator to act on.

All of the above runs as a Celery task, queued through Redis
(Valkey on Arch), so the webhook responds to Splunk immediately without
waiting for enrichment, persistence, or notification to complete.

## Project structure

```
splunk-alert-response-pipeline/
├── data/
│   └── soar.db             # SQLite database (gitignored)
├── src/
│   ├── api.py            # FastAPI webhook endpoint (Trigger)
│   ├── tasks.py           # Celery task — orchestrates the whole pipeline
│   ├── indicators.py      # Maps alert type → indicator + severity (Enrichment)
│   ├── model.py            # SQLAlchemy schema (Persistence)
│   ├── actions.py          # Maps severity → response (Decision)
│   └── notifications.py    # Email sending (smtplib)
├── locales/
│   └── pt-br/
│       └── README.md
├── .gitignore
├── README.md
└── requirements.txt
```

## Current detection

[T1110 - Brute Force (sudo authentication)](https://github.com/Kanetahk/soc-lab/blob/main/detections/T1110-sudo-bruteforce.md),
implemented in the companion repo [soc-lab](https://github.com/Kanetahk/soc-lab).

## Usage

Simulate a Splunk alert without needing Splunk itself running:
two severities, to see the branching:

```bash
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "3", "severity": "medium"}}'
curl -X POST http://127.0.0.1:8001/webhook -H "Content-Type: application/json" -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "6", "severity": "high"}}'
```

Expected result:
- `{"status": "recebido"}` returned immediately, for both
- Celery worker log shows each alert saved and notified
- Two new rows appear in `data/soar.db`, with different `severity`
- Two emails arrive, the `high` one marked `[URGENT]` and flagged as high-priority by your email client

For the alert firing for real from a live Splunk instance,
see [soc-lab](https://github.com/Kanetahk/soc-lab).

## Known limitations

- **No webhook authentication.** The `/webhook` endpoint accepts any
  POST reaching it, in this lab it's only exposed to `127.0.0.1`,
  but a production deployment would need a shared secret or signature
  check to confirm the request actually came from Splunk.
- **This detection is local, not network-based; remote blocking action is out of scope for this project.**
  `pam_faillock` already locks the account after repeated failures;
  this pipeline provides *visibility* (persistence + notification),
  not blocking, for this alert.
- **No retry on notification failure.** If the SMTP send fails
  (network issue, provider rate limit), the Celery task fails without
  a retry policy configured.
- **Single alert type implemented.** The schema and the
  `indicators.py`/`actions.py` pattern, including severity branching,
  were designed to support multiple alert types, but only T1110 exercises
  them today. A network-based alert is the natural next step to validate
  the design generalizes beyond one case.
- **Lab-scale, not production-scale.** SQLite, single Celery worker,
  single-node Splunk, sufficient to prove the pipeline, not sized for
  real traffic.

## Related projects

- [soc-lab](https://github.com/Kanetahk/soc-lab) - Splunk detection engineering, where the alerts that trigger this pipeline are built
- [siem-detection-simulator](https://github.com/Kanetahk/siem-detection-simulator) - synthetic log generator to test the detections that feed this pipeline (in development)