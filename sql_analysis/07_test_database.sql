USE CineMetrics;
GO

SELECT DB_NAME() AS CurrentDatabase;


SELECT
    SCHEMA_NAME(schema_id) AS SchemaName,
    name AS TableName
FROM sys.tables
ORDER BY SchemaName, TableName;



SELECT
    s.name AS SchemaName,
    t.name AS TableName
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
ORDER BY
    s.name,
    t.name;




SELECT COUNT(*) AS TotalMovies
FROM stg.stg_movies;


SELECT TOP 10 *
FROM stg.stg_movies
ORDER BY movie_id;


SELECT
    MIN(release_date) AS EarliestRelease,
    MAX(release_date) AS LatestRelease,
    COUNT(*) AS TotalMovies
FROM stg.stg_movies;


SELECT TOP 20
    movie_id,
    title,
    genres,
    directors,
    writers,
    cast_top_5,
    production_companies,
    production_countries
FROM stg.stg_movies;



USE CineMetrics;
GO

SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA IN ('dim', 'bridge', 'fact')
ORDER BY
    TABLE_SCHEMA,
    TABLE_NAME,
    ORDINAL_POSITION;



-- validation query to make sure the multi-value fields are formatted the way our ETL expects.

SELECT TOP 20
    movie_id,
    title,
    release_date,
    genres,
    directors,
    writers,
    cast_top_5,
    production_companies,
    production_countries,
    original_language
FROM stg.stg_movies
ORDER BY movie_id;



SELECT
    COUNT(*) AS total_movies,

    SUM(CASE WHEN genres IS NULL OR genres = '' THEN 1 ELSE 0 END)
        AS missing_genres,

    SUM(CASE WHEN directors IS NULL OR directors = '' THEN 1 ELSE 0 END)
        AS missing_directors,

    SUM(CASE WHEN writers IS NULL OR writers = '' THEN 1 ELSE 0 END)
        AS missing_writers,

    SUM(CASE WHEN cast_top_5 IS NULL OR cast_top_5 = '' THEN 1 ELSE 0 END)
        AS missing_cast,

    SUM(CASE WHEN production_companies IS NULL OR production_companies = '' THEN 1 ELSE 0 END)
        AS missing_companies,

    SUM(CASE WHEN production_countries IS NULL OR production_countries = '' THEN 1 ELSE 0 END)
        AS missing_countries,

    SUM(CASE WHEN original_language IS NULL OR original_language = '' THEN 1 ELSE 0 END)
        AS missing_languages

FROM stg.stg_movies;


-- Verify existing table structures

SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    c.column_id,
    c.name AS ColumnName,
    ty.name AS DataType,
    c.max_length,
    c.is_nullable
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.columns c
    ON t.object_id = c.object_id
JOIN sys.types ty
    ON c.user_type_id = ty.user_type_id
WHERE
    (s.name = 'dim' AND t.name IN (
        'dim_date',
        'dim_actor',
        'dim_country',
        'dim_director',
        'dim_genre',
        'dim_language',
        'dim_production_company',
        'dim_writer'
    ))
    OR
    (s.name = 'bridge' AND t.name IN (
        'bridge_movie_actor',
        'bridge_movie_genre'
    ))
    OR
    (s.name = 'fact' AND t.name = 'fact_movie')
ORDER BY
    s.name,
    t.name,
    c.column_id;

-- Validate Production company and country

SELECT TOP 20
    movie_id,
    production_companies,
    production_countries
FROM stg.stg_movies
WHERE production_companies LIKE '%|%'
   OR production_countries LIKE '%|%';




-- Final check all schema and tables

SELECT
    (SELECT COUNT(*) FROM stg.stg_movies) AS StagingRows,
    (SELECT COUNT(*) FROM fact.fact_movie) AS FactRows,

    (SELECT COUNT(*) FROM dim.dim_genre) AS Genres,
    (SELECT COUNT(*) FROM dim.dim_actor) AS Actors,
    (SELECT COUNT(*) FROM dim.dim_director) AS Directors,
    (SELECT COUNT(*) FROM dim.dim_writer) AS Writers,
    (SELECT COUNT(*) FROM dim.dim_production_company) AS ProductionCompanies,
    (SELECT COUNT(*) FROM dim.dim_country) AS Countries,
    (SELECT COUNT(*) FROM dim.dim_language) AS Languages,
    (SELECT COUNT(*) FROM dim.dim_date) AS Dates,

    (SELECT COUNT(*) FROM bridge.bridge_movie_genre) AS GenreLinks,
    (SELECT COUNT(*) FROM bridge.bridge_movie_actor) AS ActorLinks;
