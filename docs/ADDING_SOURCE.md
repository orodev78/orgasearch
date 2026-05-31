# Adding a new data source

Orgasearch uses a plugin model: each source implements `PartnerSource` and is registered at startup.

## Steps

### 1. Create the adapter module

Add `app/sources/<id>.py` implementing:

- `id` — stable identifier (e.g. `crossref`)
- `display_name` — human label
- `supported_lookup_keys()` — external id keys this source can resolve in phase 2
- `enabled()` — return `False` if required config is missing
- `search(ctx)` — text search → `list[PartnerResult]`
- `lookup(ctx, key, value)` — id lookup → `PartnerResult | None`

Export a factory:

```python
def get_source() -> MySource:
    return MySource()
```

Keep all JSON → `PartnerResult` mapping inside this module.

### 2. Register in `config/sources.yaml`

```yaml
sources:
  mysource:
    enabled: true
    timeout_seconds: 5
    default_per_source: 10
    requires_env: [MY_SOURCE_API_KEY]
```

### 3. Add to builtin list

In `app/sources/registry.py`, add your id to `BUILTIN_SOURCES`.

### 4. Configure ID expansion (optional)

In `config/id_expansion.yaml`, add rules so other sources can resolve your external ids:

```yaml
rules:
  - id_key: mysource
    resolve_on_sources: [ror, wikidata]
```

### 5. Dedup keys (optional)

If you introduce a new cross-source identifier, add it to `config/dedup_rules.yaml` under `priority_keys`.

### 6. Tests

- Capture a sample API response as `tests/fixtures/<id>_sample.json`
- Add `tests/test_mapping_<id>.py` asserting field mapping

No changes to `app/api/v1/search.py` or the orchestrator are required.
