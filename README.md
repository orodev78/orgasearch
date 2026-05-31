# Orgasearch

Metasearch API for institutional partners (universities, labs, companies) across **ROR**, **Wikidata**, **HAL**, and **OpenAlex**.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
copy .env.example .env          # set OPENALEX_API_KEY, WIKIDATA_USER_AGENT
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/api/doc
- Health: http://localhost:8000/health
- Search: `GET /v1/partners/search?q=CNRS&lang=fr,en`

## Configuration

| Variable | Description |
|----------|-------------|
| `OPENALEX_API_KEY` | Required for OpenAlex (free at openalex.org/settings/api) |
| `WIKIDATA_USER_AGENT` | Required by Wikimedia policy |
| `CACHE_URL` | Optional Redis URL (`redis://localhost:6379/0`); in-memory TTL cache if unset |
| `SEARCH_TIMEOUT_SECONDS` | Global HTTP timeout (default 8) |
| `RATE_LIMIT_GLOBAL` | Default cap for all routes (default `120/minute`) |
| `RATE_LIMIT_SEARCH` | Stricter cap for `/v1/partners/search` (default `30/minute`) |
| `RATE_LIMIT_READ` | Cap for `/health` and `/v1/sources` (default `60/minute`) |
| `SEARCH_MAX_QUERY_LENGTH` | Max characters for `q` (default `500`) |
| `SEARCH_MAX_LANGS` | Max languages in `langs` (default `10`) |
| `SEARCH_MAX_EXPANSIONS_DEFAULT` | Default phase-2 lookups (default `12`) |
| `SEARCH_MIN_SCORE` | Drop results below this relevance score after ranking (default `0.45`, range 0–1) |

See [`.env.example`](.env.example) and [`config/sources.yaml`](config/sources.yaml).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status and version |
| GET | `/v1/sources` | Registered sources |
| GET | `/v1/partners/search` | Metasearch (phase 1 + optional expansion) |
| GET | `/v1/partners/{source}/{id}` | Fetch one partner by native source id (same JSON as search) |
| GET | `/api/doc` | Swagger UI |

Search parameters: `q` (max 500 chars), `langs` (max 10 codes by default, see `SEARCH_MAX_LANGS`), `sources`, `limit`, `per_source`, `country`, `type`, `expand`, `merge`, `max_expansions` (default 12, max 50).

Lookup parameters: `source` (`ror`, `wikidata`, `hal`, `openalex`), native `id` in the path (e.g. ROR `05tj8pb04`, Wikidata `Q308329`, HAL `1821780`), `langs`, `expand` (default **false**), `merge`, `limit`, `max_expansions`. Does not apply `SEARCH_MIN_SCORE`. Returns **404** if the record is not found.

Never commit `.env` (see `.gitignore`); copy from `.env.example` only.

By default (`merge=false`), each source returns **its own row** with source-specific `labels`. Use `merge=true` to fuse duplicates that share ROR/Wikidata/OpenAlex IDs.

Results are ranked by a **relevance score** (`score`, 0–1): source rank (ROR/HAL position) plus token overlap with `q` and optional `country` filter bonus. Rows below `SEARCH_MIN_SCORE` (default `0.45`) are removed after ranking on **search** only (not on lookup-by-id).

## Docker

```bash
docker build -t orgasearch .
docker run -p 8000:8000 --env-file .env orgasearch
```

## Apache reverse proxy (WAMP)

Enable `proxy` and `proxy_http`, then:

```apache
ProxyPass /orgasearch http://127.0.0.1:8000
ProxyPassReverse /orgasearch http://127.0.0.1:8000
```

Run Orgasearch separately (`uvicorn` or Docker). WAMP stays as the front door.

## Tests

```bash
pytest
```

Mapping tests use JSON fixtures under `tests/fixtures/`. Live API tests can be marked `@pytest.mark.external`.

## Adding a source

See [docs/ADDING_SOURCE.md](docs/ADDING_SOURCE.md).

## Architecture

- **Phase 1**: parallel text search on active sources
- **Phase 2** (`expand=true`): lookup by `external_ids` per `config/id_expansion.yaml`
- **Merge**: deduplicate by ROR / Wikidata / OpenAlex ids, union labels and external ids
