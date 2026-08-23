# Backend — Concurso Mestre IA

API FastAPI da plataforma. Consulte a documentação de arquitetura em `../docs/`.

## Desenvolvimento local (sem Docker)

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env      # ajuste MYSQL_HOST=127.0.0.1 se o banco for local
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload
```

## Testes

```bash
pytest                 # roda sobre SQLite, sem infraestrutura externa
ruff check app tests
mypy app
```
