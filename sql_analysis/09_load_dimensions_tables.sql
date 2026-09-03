USE CineMetrics;
GO


-- Genre

INSERT INTO dim.dim_genre (GenreName)
SELECT DISTINCT
    LTRIM(RTRIM(value)) AS GenreName
FROM stg.stg_movies
CROSS APPLY STRING_SPLIT(genres, '|')
WHERE NULLIF(LTRIM(RTRIM(value)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_genre g
      WHERE g.GenreName = LTRIM(RTRIM(value))
  );


SELECT *
FROM dim.dim_genre
ORDER BY GenreName;


-- Actor

INSERT INTO dim.dim_actor (ActorName)
SELECT DISTINCT
    LTRIM(RTRIM(value)) AS ActorName
FROM stg.stg_movies
CROSS APPLY STRING_SPLIT(cast_top_5, '|')
WHERE NULLIF(LTRIM(RTRIM(value)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_actor a
      WHERE a.ActorName = LTRIM(RTRIM(value))
  );


SELECT TOP 20 *
FROM dim.dim_actor
ORDER BY ActorName;


-- Director

INSERT INTO dim.dim_director (DirectorName)
SELECT DISTINCT
    LTRIM(RTRIM(directors))
FROM stg.stg_movies
WHERE NULLIF(LTRIM(RTRIM(directors)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_director d
      WHERE d.DirectorName = LTRIM(RTRIM(directors))
  );


-- Writer

INSERT INTO dim.dim_writer (WriterName)
SELECT DISTINCT
    LTRIM(RTRIM(writers))
FROM stg.stg_movies
WHERE NULLIF(LTRIM(RTRIM(writers)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_writer w
      WHERE w.WriterName = LTRIM(RTRIM(writers))
  );



-- Production Company

INSERT INTO dim.dim_production_company (ProductionCompanyName)
SELECT DISTINCT
    LTRIM(RTRIM(production_companies))
FROM stg.stg_movies
WHERE NULLIF(LTRIM(RTRIM(production_companies)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_production_company pc
      WHERE pc.ProductionCompanyName =
            LTRIM(RTRIM(production_companies))
  );


-- Country

INSERT INTO dim.dim_country (CountryName)
SELECT DISTINCT
    LTRIM(RTRIM(production_countries))
FROM stg.stg_movies
WHERE NULLIF(LTRIM(RTRIM(production_countries)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_country c
      WHERE c.CountryName =
            LTRIM(RTRIM(production_countries))
  );



-- Language

INSERT INTO dim.dim_language (LanguageCode)
SELECT DISTINCT
    LTRIM(RTRIM(original_language))
FROM stg.stg_movies
WHERE NULLIF(LTRIM(RTRIM(original_language)), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_language l
      WHERE l.LanguageCode =
            LTRIM(RTRIM(original_language))
  );



----------------------------

-- Date

INSERT INTO dim.dim_date
(
    DateKey,
    FullDate,
    Year,
    Quarter,
    QuarterName,
    Month,
    MonthName,
    MonthShortName,
    Day,
    DayOfWeek,
    DayName,
    IsWeekend
)
SELECT DISTINCT
    CONVERT(INT, CONVERT(VARCHAR(8), CAST(release_date AS DATE), 112)) AS DateKey,
    CAST(release_date AS DATE) AS FullDate,
    YEAR(release_date) AS Year,
    DATEPART(QUARTER, release_date) AS Quarter,
    'Q' + CAST(DATEPART(QUARTER, release_date) AS VARCHAR(1)) AS QuarterName,
    MONTH(release_date) AS Month,
    DATENAME(MONTH, release_date) AS MonthName,
    LEFT(DATENAME(MONTH, release_date), 3) AS MonthShortName,
    DAY(release_date) AS Day,
    DATEPART(WEEKDAY, release_date) AS DayOfWeek,
    DATENAME(WEEKDAY, release_date) AS DayName,
    CASE
        WHEN DATEPART(WEEKDAY, release_date) IN (1, 7)
        THEN 1
        ELSE 0
    END AS IsWeekend
FROM stg.stg_movies
WHERE release_date IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM dim.dim_date d
      WHERE d.FullDate = CAST(stg.stg_movies.release_date AS DATE)
  );



----------------------------------------------------
-- Verify dimensions

SELECT 'Genre' AS Dimension, COUNT(*) AS Rows
FROM dim.dim_genre

UNION ALL

SELECT 'Actor', COUNT(*)
FROM dim.dim_actor

UNION ALL

SELECT 'Director', COUNT(*)
FROM dim.dim_director

UNION ALL

SELECT 'Writer', COUNT(*)
FROM dim.dim_writer

UNION ALL

SELECT 'Production Company', COUNT(*)
FROM dim.dim_production_company

UNION ALL

SELECT 'Country', COUNT(*)
FROM dim.dim_country

UNION ALL

SELECT 'Language', COUNT(*)
FROM dim.dim_language

UNION ALL

SELECT 'Date', COUNT(*)
FROM dim.dim_date;



-- check the staging → dimension matches

SELECT
    COUNT(*) AS TotalMovies,

    SUM(CASE
        WHEN d.DateKey IS NOT NULL THEN 1 ELSE 0
    END) AS DateMatched,

    SUM(CASE
        WHEN dr.DirectorKey IS NOT NULL THEN 1 ELSE 0
    END) AS DirectorMatched,

    SUM(CASE
        WHEN w.WriterKey IS NOT NULL THEN 1 ELSE 0
    END) AS WriterMatched,

    SUM(CASE
        WHEN pc.ProductionCompanyKey IS NOT NULL THEN 1 ELSE 0
    END) AS CompanyMatched,

    SUM(CASE
        WHEN c.CountryKey IS NOT NULL THEN 1 ELSE 0
    END) AS CountryMatched,

    SUM(CASE
        WHEN l.LanguageKey IS NOT NULL THEN 1 ELSE 0
    END) AS LanguageMatched

FROM stg.stg_movies s

LEFT JOIN dim.dim_date d
    ON d.FullDate = TRY_CAST(s.release_date AS DATE)

LEFT JOIN dim.dim_director dr
    ON dr.DirectorName = NULLIF(LTRIM(RTRIM(s.directors)), '')

LEFT JOIN dim.dim_writer w
    ON w.WriterName = NULLIF(LTRIM(RTRIM(s.writers)), '')

LEFT JOIN dim.dim_production_company pc
    ON pc.ProductionCompanyName =
       NULLIF(LTRIM(RTRIM(s.production_companies)), '')

LEFT JOIN dim.dim_country c
    ON c.CountryName =
       NULLIF(LTRIM(RTRIM(s.production_countries)), '')

LEFT JOIN dim.dim_language l
    ON l.LanguageCode =
       NULLIF(LTRIM(RTRIM(s.original_language)), '');