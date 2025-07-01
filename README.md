# OpenSearch Prometheus indices metrics exporter

This simple container lists all your indices, groups them by pattern then exports their summary metrics in Prometheus-compatible format.

This is useful to track your logging indices resources consumption over time

## Usage

### Docker

### Kubernetes

## Development guideline

Load the venv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Then start the debugger with `src/app.py`
