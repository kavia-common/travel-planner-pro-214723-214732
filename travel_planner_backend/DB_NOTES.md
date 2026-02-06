# Database notes (Destinations search)

This backend adds trigram-based GIN indexes to speed up `ILIKE '%query%'` searches for destinations.

## Required PostgreSQL extension

These indexes require the `pg_trgm` extension:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## Notes

- If you are using Alembic migrations, ensure the extension creation and indexes are applied as part of your migration flow.
- If you are using SQLAlchemy `Base.metadata.create_all()`, the indexes will be created automatically *after* the extension exists.
- If the extension is missing, PostgreSQL will error when attempting to create the indexes using `gin_trgm_ops`.
