# Named OSLC federation profiles

Quarto-Needs keeps OSLC connection policy separate from the canonical engineering model **without creating a second project configuration file**. Named federation profiles live under `[federation.oslc.profiles.*]` in `.quarto-needs.toml`.

The section may be versioned because it contains endpoint identity and bounded retrieval policy, **not credential values**. While federation remains read-only and does not import remote resources into the canonical graph, this operational section is deliberately excluded from the graph configuration fingerprint.

A profile declares one read-only Service Provider boundary:

```toml
[federation.oslc.profiles.production]
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

## One file, two semantic domains

`.quarto-needs.toml` now contains both local engineering-model configuration and bounded external-adapter configuration, but they remain semantically distinct:

- `profile`, `types`, `relations`, governance, policies, constraints, variants, gates, and graph settings participate in canonical engineering configuration;
- `federation.oslc.profiles` controls read-only external connectivity and currently does **not** participate in the canonical graph fingerprint.

This distinction is intentional. Changing a timeout, cache directory, Service Provider URI, or environment-variable binding must not silently change the meaning of authored requirements while remote data remains external to the graph.

If future Quarto-Needs versions allow remote requirements to be imported into the canonical graph, the fingerprint/provenance contract must be revised explicitly before that feature is enabled.

## Migration from the experimental parallel file

The temporary `.quarto-needs-oslc.toml` format is retired. If it is present, `quarto-needs oslc discover --profile ...` fails with migration guidance rather than silently choosing between two sources.

Move:

```toml
[profiles.production]
service-provider-uri = "https://provider.example/oslc/sp/requirements"
```

to `.quarto-needs.toml` as:

```toml
[federation.oslc.profiles.production]
service-provider-uri = "https://provider.example/oslc/sp/requirements"
```
