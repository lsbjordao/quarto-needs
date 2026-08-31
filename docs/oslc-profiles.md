# Named OSLC federation profiles

Quarto-Needs keeps OSLC connection policy separate from the canonical engineering model. Named federation profiles live in `.quarto-needs-oslc.toml`; the file may be versioned because it contains endpoint names and budgets, **not credential values**.

A profile declares one read-only Service Provider boundary:

```toml
[profiles.production]
service-provider-uri = "https://provider.example/oslc/sp/requirements"
cache-dir = ".quarto-needs/oslc/production"
max-age-seconds = 3600
allow-stale = false
timeout-seconds = 10.0
max-bytes = 2000000
max-redirects = 3
max-nodes = 5000
fetch-shapes = true
bearer-token-env = "QUARTO_NEEDS_OSLC_PRODUCTION_TOKEN"
```

The value of `bearer-token-env` is only the **name** of an environment variable. The bearer token itself must stay outside TOML, Git, cache manifests, generated graph projections, evidence, and CLI output.

Use a named profile with:

```bash
export QUARTO_NEEDS_OSLC_PRODUCTION_TOKEN='...'
quarto-needs oslc discover --profile production
```

JSON output is available for automation:

```bash
quarto-needs oslc discover --profile production --format json
```

Explicit CLI values override the selected profile for that invocation:

```bash
quarto-needs oslc discover \
  --profile production \
  --max-bytes 500000 \
  --max-nodes 1000 \
  --no-shapes
```

A Service Provider URI may also be supplied directly instead of using a profile. URI and `--profile` are mutually exclusive.

## Policy fields

| Key | Meaning |
| --- | --- |
| `service-provider-uri` | Absolute HTTP(S) OSLC Service Provider URI |
| `cache-dir` | Project-relative or absolute cache root |
| `max-age-seconds` | Fresh-cache lifetime; zero is allowed |
| `allow-stale` | Permit stale cache only as an offline fallback |
| `timeout-seconds` | Per-request timeout |
| `max-bytes` | Maximum response bytes |
| `max-redirects` | Maximum same-origin redirects |
| `max-nodes` | Maximum expanded RDF/JSON-LD nodes |
| `fetch-shapes` | Fetch and parse advertised Resource Shapes |
| `bearer-token-env` | Environment-variable name containing the bearer token |

Unknown keys fail explicitly. A `bearer-token` key is deliberately unsupported so a secret cannot be normalized into the profile model by accident.

## Why this is a separate file

`.quarto-needs.toml` currently describes the canonical local engineering model and participates in semantic/configuration fingerprints. OSLC profiles describe **external connectivity policy**. Keeping those concerns separate in the first federation milestone avoids making a remote endpoint or credential-binding choice part of local engineering semantics.

A future configuration unification may provide one schema and migration path, but it must preserve this distinction: changing connectivity must not silently change the meaning of authored requirements.
