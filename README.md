# experiment-closedclaw-find-me-a-book

## Environment setup

Use `requirements.txt` as the canonical dependency manifest.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Testing

Use `python -m pytest` as the canonical test command for local development and CI.

```bash
python -m pytest
```
