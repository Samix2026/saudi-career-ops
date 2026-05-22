# data/

Reference data for Saudi Career Ops. No personally identifiable information is stored here.

## Files

| File | Description |
|------|-------------|
| `saudi-job-sources.json` | Registry of job platforms relevant to the Saudi labor market. |
| `sources.json` | Placeholder for tracked external data sources and update status. |

## Schemas

JSON Schema definitions live in `data/schemas/`. Each schema targets a specific data file.

| Schema | Validates |
|--------|-----------|
| `schemas/saudi-job-sources.schema.json` | `saudi-job-sources.json` |

Schemas are written to Draft-07. They are reference documents — validation is run
programmatically via `scripts/validate-data.py`.

## Validation

Run the validator from the repository root:

```bash
python scripts/validate-data.py
```

The script uses only the Python standard library (Python 3.9+). No external packages required.

Optional flags:

```bash
python scripts/validate-data.py --verbose          # detailed output on success
python scripts/validate-data.py --data path/to/file.json  # validate a different file
```

Exit code is `0` on success, `1` on any validation failure.

### If you want full JSON Schema Draft-07 validation

The validator script implements the schema's constraints manually. If you need
full Draft-07 compliance (e.g., for CI or third-party tooling), install `jsonschema`:

```bash
pip install jsonschema
```

Then validate directly:

```bash
python -c "
import json, jsonschema
data = json.load(open('data/saudi-job-sources.json'))
schema = json.load(open('data/schemas/saudi-job-sources.schema.json'))
jsonschema.validate(data, schema)
print('valid')
"
```

Note: the `format: uri` keyword in the schema requires the `format` checker:

```bash
python -c "
import json, jsonschema
data = json.load(open('data/saudi-job-sources.json'))
schema = json.load(open('data/schemas/saudi-job-sources.schema.json'))
jsonschema.validate(data, schema, format_checker=jsonschema.FormatChecker())
print('valid')
"
```

## Rules

- No PII. No real names, national ID numbers, Iqama numbers, phone numbers, or email addresses.
- All entries in `saudi-job-sources.json` must have a documented source or be publicly verifiable.
- Run `python scripts/validate-data.py` before committing changes to any data file.
