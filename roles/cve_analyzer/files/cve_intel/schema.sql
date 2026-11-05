-- CVE Intelligence — dedicated schema on Grafana PostgreSQL.
-- Does NOT touch Grafana core tables (public.dashboard, user, etc.).
-- Idempotent: safe to re-run.

CREATE SCHEMA IF NOT EXISTS cve_intel;

CREATE TABLE IF NOT EXISTS cve_intel.rh_cve_published (
    cve_id               TEXT PRIMARY KEY,
    threat_severity      TEXT NOT NULL DEFAULT '',
    public_date          TIMESTAMPTZ,
    first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_collected_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bugzilla_id          TEXT,
    bugzilla_description TEXT,
    cvss3_score          DOUBLE PRECISION,
    cvss3_vector         TEXT,
    cwe                  TEXT,
    statement            TEXT,
    details              TEXT,
    resource_url         TEXT,
    portal_url           TEXT,
    advisories           JSONB NOT NULL DEFAULT '[]'::jsonb,
    products             JSONB NOT NULL DEFAULT '[]'::jsonb,
    package_states       JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_list             JSONB,
    raw_detail           JSONB
);

-- Backfill/rename safety for earlier scaffold without first_seen_at
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'cve_intel' AND table_name = 'rh_cve_published'
      AND column_name = 'first_collected_at'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'cve_intel' AND table_name = 'rh_cve_published'
      AND column_name = 'first_seen_at'
  ) THEN
    ALTER TABLE cve_intel.rh_cve_published
      ADD COLUMN first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    UPDATE cve_intel.rh_cve_published
      SET first_seen_at = first_collected_at
      WHERE first_seen_at IS NULL OR first_seen_at = NOW();
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS rh_cve_published_public_date_idx
    ON cve_intel.rh_cve_published (public_date DESC);

CREATE INDEX IF NOT EXISTS rh_cve_published_first_seen_idx
    ON cve_intel.rh_cve_published (first_seen_at DESC);

CREATE INDEX IF NOT EXISTS rh_cve_published_severity_idx
    ON cve_intel.rh_cve_published (threat_severity);

CREATE TABLE IF NOT EXISTS cve_intel.rh_cve_rhacs_match (
    cve_id                  TEXT NOT NULL REFERENCES cve_intel.rh_cve_published (cve_id) ON DELETE CASCADE,
    cluster                 TEXT NOT NULL DEFAULT '',
    rhacs_namespace         TEXT NOT NULL DEFAULT '',
    severity                TEXT NOT NULL DEFAULT '',
    image                   TEXT NOT NULL DEFAULT '',
    component               TEXT NOT NULL DEFAULT '',
    first_detected_in_rhacs TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_detected_in_rhacs  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finding_count           INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (cve_id, cluster, rhacs_namespace, severity, image, component)
);

CREATE INDEX IF NOT EXISTS rh_cve_rhacs_match_cluster_idx
    ON cve_intel.rh_cve_rhacs_match (cluster);

CREATE INDEX IF NOT EXISTS rh_cve_rhacs_match_namespace_idx
    ON cve_intel.rh_cve_rhacs_match (rhacs_namespace);

CREATE OR REPLACE VIEW cve_intel.rh_cve_daily_summary AS
SELECT
    (public_date AT TIME ZONE 'UTC')::date AS pub_day,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'critical') AS critical,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'important') AS important,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'moderate') AS moderate,
    COUNT(*) FILTER (WHERE lower(threat_severity) = 'low') AS low
FROM cve_intel.rh_cve_published
WHERE public_date IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

-- Last successful collector / matcher runs (freshness panels).
CREATE TABLE IF NOT EXISTS cve_intel.pipeline_status (
    pipeline          TEXT PRIMARY KEY,
    last_success_at   TIMESTAMPTZ NOT NULL,
    last_input_count  INTEGER,
    last_output_count INTEGER,
    details           JSONB NOT NULL DEFAULT '{}'::jsonb
);
