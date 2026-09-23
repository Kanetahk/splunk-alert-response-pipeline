# Python SOAR integrated with Splunk
A SOAR (Security Orchestration, Automation, and Response) system that
receives alerts from a Splunk deployment and automates the response
pipeline: **Trigger → Enrichment → Decision → Action**.

*Read this in: [Português](./locales/pt-BR/README.md)*

## Built with
Python 3.14 · FastAPI · Celery · Redis (Valkey) · SQLAlchemy · Pydantic

## Architecture
- **Trigger** — FastAPI endpoint (`api.py`) receiving Splunk's native
  Webhook alert action, validated as a generic `{search_name, result}`
  shape (no assumption about specific alert fields).
- **Enrichment** — `indicators.py` maps each alert type to the relevant
  indicator (e.g. `user` for local brute-force, `source_ip` for
  network-based alerts once implemented).
- **Decision/persistence** — every processed alert is stored in SQLite
  via SQLAlchemy (`model.py`), keyed by indicator type/value.
- **Action** — `actions.py` maps each alert type to a response;
  currently email notification via `smtplib` (`notifications.py`).
  Remote/blocking action is out of scope for this project — the only
  detection implemented so far is local, with no network indicator to
  act on.

All of the above runs as a Celery task, queued through Redis (Valkey on
Arch), so the webhook responds to Splunk immediately without waiting
for enrichment, persistence, or notification to complete.

## Project structure
```
├── src/
│   ├── api.py           # FastAPI webhook endpoint (Trigger)
│   ├── tasks.py          # Celery task — orchestrates the whole pipeline
│   ├── indicators.py     # Maps alert type → indicator (Enrichment)
│   ├── model.py           # SQLAlchemy schema (Decision/persistence)
│   ├── actions.py         # Maps alert type → response (Action)
│   └── notifications.py   # Email sending (smtplib)
├── data/
│   └── soar.db           # SQLite database (gitignored)
└── requirements.txt
```

## Current detection
[T1110 - Brute Force (sudo authentication)](https://github.com/Kanetahk/soc-lab/blob/main/detections/T1110-sudo-bruteforce.md),
implemented in the companion repo [soc-lab](https://github.com/Kanetahk/soc-lab).

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requires Redis or Valkey installed and running (e.g. `sudo pacman -S valkey && sudo systemctl enable --now valkey` on Arch).

Environment variables required (`.env`, never committed):
```
GITHUB_TOKEN=
EMAIL_SENDER=
EMAIL_APP_PASSWORD=
EMAIL_RECIPIENT=
```

## Usage
Start both processes:

```bash
celery -A tasks worker --loglevel=info
uvicorn api:app --host 0.0.0.0 --port 8001
```

Simulate a Splunk alert without needing Splunk itself running:

```bash
curl -X POST http://127.0.0.1:8001/webhook \
  -H "Content-Type: application/json" \
  -d '{"search_name": "T1110 - Brute Force (sudo authentication)", "result": {"user": "kanetah", "attempts": "3"}}'
```

Expected result:
- `{"status": "recebido"}` returned immediately
- Celery worker log shows the alert saved and the notification sent
- A new row appears in `soar.db`
- An email arrives at `EMAIL_RECIPIENT`

For the alert firing for real from a live Splunk instance, see
[soc-lab](https://github.com/Kanetahk/soc-lab).

## Known limitations

- **No webhook authentication.** The `/webhook` endpoint accepts any
  POST reaching it — in this lab it's only exposed to `127.0.0.1`, but
  a production deployment would need a shared secret or signature
  check to confirm the request actually came from Splunk.
- **This detection is local, not network-based; remote blocking action is out of scope for this project.**
 `pam_faillock` already locks the account after repeated failures;
  this pipeline provides *visibility* (persistence + notification),
  not blocking, for this alert.
- **No retry on notification failure.** If the SMTP send fails
  (network issue, provider rate limit), the Celery task fails without
  a retry policy configured.
- **Single alert type implemented.** The schema (`indicator_type` /
  `indicator_value`) and the `indicators.py`/`actions.py` pattern were
  designed to support multiple alert types, but only T1110 has a rule
  today — adding a network-based alert is the natural next step to
  validate the design actually generalizes.
- **Lab-scale, not production-scale.** SQLite, single Celery worker,
  single-node Splunk — sufficient to prove the pipeline, not sized for
  real traffic.