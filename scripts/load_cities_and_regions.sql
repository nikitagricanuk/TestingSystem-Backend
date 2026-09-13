-- One-time seed for regions/settlements. Run after `docker compose up -d db`:
--   docker compose exec db psql -U "$DB_USER" -d "$DB_NAME" -f /import/scripts/load_cities_and_regions.sql
-- Requires the db service to also mount ./data:/import/data:ro (see compose.yaml).

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 0) Make sure the unique constraints exist (use indexes with IF NOT EXISTS)
CREATE UNIQUE INDEX IF NOT EXISTS regions_region_key
  ON regions (region);

-- Fix legacy uniqueness on settlements.name (causes duplicates like multiple "Октябрьский")
ALTER TABLE settlements DROP CONSTRAINT IF EXISTS settlements_name_key;
-- Some setups might have created a standalone unique index instead of a constraint
DROP INDEX IF EXISTS settlements_name_key;
DROP INDEX IF EXISTS settlements_name_idx;

CREATE UNIQUE INDEX IF NOT EXISTS settlements_natural_key
  ON settlements (name, type, region_id);

-- 1) Temp staging table (safe to drop; TEMP is per-session)
DROP TABLE IF EXISTS staging_settlements;
CREATE TEMP TABLE staging_settlements (
    name        text,
    type        text,
    region_name text
);

\echo Loading regions into staging...
DROP TABLE IF EXISTS staging_regions;
CREATE TEMP TABLE staging_regions (
    region text
);
\copy staging_regions(region) FROM '/import/data/regions.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo Upserting regions (generating UUIDs)...
INSERT INTO regions (id, region)
SELECT gen_random_uuid(), r.region
FROM (
    SELECT DISTINCT region FROM staging_regions WHERE region IS NOT NULL
) r
ON CONFLICT (region) DO NOTHING;

\echo Loading settlements into staging...
\copy staging_settlements(name, type, region_name) FROM '/import/data/settlements.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo Inserting settlements (resolving region_id)...
INSERT INTO settlements (id, name, type, region_id)
SELECT gen_random_uuid(), s.name, s.type, r.id
FROM staging_settlements s
JOIN regions r ON r.region = s.region_name
ON CONFLICT (name, type, region_id) DO NOTHING;

\echo Done.