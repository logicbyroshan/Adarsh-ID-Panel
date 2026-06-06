# Adarsh ID Panel: Known Limitations

This document lists design boundaries, hardware-constrained performance limits, and system constraints in the v1.2.0 release.

---

## 1. System Scale Boundaries

- **Dynamic Fields Limit**:
  * **Constraint**: A table schema is limited to 100 configured dynamic `Field` attributes.
  * **Rationale**: Exceeding 100 columns causes heavy browser layout rendering overhead and increases DB parsing costs during cards serialization.
- **Concurrent Import Cap**:
  * **Constraint**: A maximum of 5 Excel/ZIP batch import processes can run concurrently.
  * **Rationale**: Import runs are memory-intensive (extracting ZIP archives and parsing XLSX rows). Celery queues enforce worker boundaries to prevent RAM exhaustion.
- **Maximum Image Upload Resolution**:
  * **Constraint**: Individual card headshot image uploads are capped at 5 Megabytes (MB).
  * **Rationale**: Prevents disk space exhaustion and keeps document compilation times (PDF generation) fast.

---

## 2. Dynamic Schema Limitations

- **Schema Renaming**:
  * **Constraint**: Renaming a `Field` key does not retroactively rewrite card data JSON keys in existing card rows.
  * **Workaround**: We recommend creating a new field and running an import to migrate historical values, or keeping naming updates minimal.
- **Type Conversions**:
  * **Constraint**: In-place field type changes (e.g. converting a `STRING` field containing text to a `NUMBER` field) are validated strictly. If any existing cards fail the new format validation, the change is blocked.

---

## 3. Storage & Environment Constraints

- **Local Storage Limitations**:
  * If running `STORAGE_PROVIDER=local`, horizontal web nodes cannot share files unless mounted on a shared network drive (NFS/EFS).
  * We recommend deploying with `STORAGE_PROVIDER=r2` (Cloudflare R2) or `minio` in multi-node production setups.
