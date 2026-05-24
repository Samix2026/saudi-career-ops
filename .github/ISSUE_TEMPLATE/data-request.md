---
name: Data Request: Expand entities database
about: Request verified company entity data to improve Nitaqat engine accuracy.
labels: data, good first issue
assignees: []
---

### Title: 📊 Data Request: Expand entities database

#### Description
We are building a robust intelligence layer to accurately validate Saudi entity types (PIF, RHQ, SEZ, Private). Currently, our engine relies on a baseline configuration, but we need to expand our local database to improve accuracy.

We are looking for contributions to populate `data/entities_db.tsv` with verified information.

#### How to contribute
Please provide data in the following TSV format:
`Company Name | Org Type (RHQ/PIF/Gov/Private) | Nitaqat Status | Qiwa Integration | Notes`

**Example:**
`NEOM | PIF | Platinum | High | Giga-project`

If you have access to verified information or public lists of RHQ/PIF entities, please submit a PR or comment the data below.
