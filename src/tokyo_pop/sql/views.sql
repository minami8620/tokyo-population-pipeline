-- Analytical views over the processed Parquet files.
-- {processed} is replaced with the processed-data directory at connection time.

CREATE OR REPLACE VIEW population AS
SELECT * FROM read_parquet('{processed}/population/*.parquet');

-- Each release reports the movement during the month before as_of; period is that month.
CREATE OR REPLACE VIEW movement AS
SELECT (as_of - INTERVAL 1 MONTH)::DATE AS period, *
FROM read_parquet('{processed}/movement/*.parquet');

-- Prefecture-wide headline numbers per month.
CREATE OR REPLACE VIEW monthly_total AS
SELECT
    as_of,
    population,
    households,
    change_from_prev_month,
    round(population / households, 3) AS persons_per_household
FROM population
WHERE level = 0
ORDER BY as_of;

-- One row per municipality per month, with derived metrics and growth over
-- 12 months (NULL until 13 months are loaded) and since the first loaded month.
CREATE OR REPLACE VIEW municipality_monthly AS
SELECT
    as_of,
    area_code,
    area_name,
    area_name_en,
    starts_with(area_code, '131') AS is_ward,
    population,
    households,
    round(population / area_km2) AS density_per_km2,
    round(100.0 * male / female, 1) AS sex_ratio,
    change_from_prev_month,
    population - lag(population, 12) OVER w AS change_12m,
    round(100.0 * (population / lag(population, 12) OVER w - 1), 2) AS growth_12m_pct,
    population - first_value(population) OVER w AS change_since_start,
    round(100.0 * (population / first_value(population) OVER w - 1), 2) AS growth_since_start_pct
FROM population
WHERE level = 4
WINDOW w AS (PARTITION BY area_code ORDER BY as_of);

-- Latest month only, ranked by population.
CREATE OR REPLACE VIEW municipality_latest AS
SELECT
    *,
    rank() OVER (ORDER BY population DESC) AS population_rank
FROM municipality_monthly
WHERE as_of = (SELECT max(as_of) FROM population);

-- Where does each municipality's change come from? Summed over every month loaded.
CREATE OR REPLACE VIEW change_components AS
SELECT
    area_code,
    any_value(area_name) AS area_name,
    any_value(area_name_en) AS area_name_en,
    nationality,
    count(*) AS months,
    sum(net_change)::BIGINT AS net_change,
    sum(interpref_net)::BIGINT AS from_other_prefectures,
    sum(intrapref_net)::BIGINT AS from_within_tokyo,
    sum(natural_net)::BIGINT AS natural_change,
    sum(births)::BIGINT AS births,
    sum(deaths)::BIGINT AS deaths,
    sum(other_change)::BIGINT AS other_change
FROM movement
GROUP BY area_code, nationality;

-- Japanese vs foreign residents: net change per month, prefecture-wide.
-- census_adjustment is the census rebasing correction that the source only
-- reports in the total (non-zero only in rebasing months).
CREATE OR REPLACE VIEW nationality_trend AS
SELECT
    period,
    sum(net_change) FILTER (WHERE nationality = 'japanese')::BIGINT AS japanese_net,
    sum(net_change) FILTER (WHERE nationality = 'foreign')::BIGINT AS foreign_net,
    sum(net_change) FILTER (WHERE nationality = 'total')::BIGINT
        - sum(net_change) FILTER (WHERE nationality <> 'total')::BIGINT AS census_adjustment,
    sum(natural_net) FILTER (WHERE nationality = 'japanese')::BIGINT AS japanese_natural,
    sum(interpref_net) FILTER (WHERE nationality = 'japanese')::BIGINT AS japanese_migration
FROM movement
WHERE level = 0
GROUP BY period
ORDER BY period;
