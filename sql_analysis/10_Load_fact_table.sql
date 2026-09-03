USE CineMetrics;
GO


INSERT INTO fact.fact_movie
(
    MovieID,
    DateKey,
    DirectorKey,
    WriterKey,
    ProductionCompanyKey,
    CountryKey,
    LanguageKey,
    Title,
    Overview,
    Tagline,
    Homepage,
    PosterPath,
    BackdropPath,
    RuntimeMinutes,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Popularity,
    TMDB_Rating,
    TMDB_VoteCount,
    MovieStatus,
    IMDb_ID
)
SELECT
    s.movie_id,

    d.DateKey,

    dr.DirectorKey,

    w.WriterKey,

    pc.ProductionCompanyKey,

    c.CountryKey,

    l.LanguageKey,

    s.title,

    s.overview,

    s.tagline,

    s.homepage,

    s.poster_path,

    s.backdrop_path,

    TRY_CAST(s.runtime AS INT),

    TRY_CAST(s.budget AS BIGINT),

    TRY_CAST(s.revenue AS BIGINT),

    CASE
        WHEN TRY_CAST(s.revenue AS BIGINT) IS NOT NULL
         AND TRY_CAST(s.budget AS BIGINT) IS NOT NULL
         AND TRY_CAST(s.revenue AS BIGINT) > 0
         AND TRY_CAST(s.budget AS BIGINT) > 0
        THEN
            TRY_CAST(s.revenue AS BIGINT)
            - TRY_CAST(s.budget AS BIGINT)
        ELSE NULL
    END AS Profit,

    CASE
        WHEN TRY_CAST(s.budget AS BIGINT) > 0
         AND TRY_CAST(s.revenue AS BIGINT) IS NOT NULL
        THEN
            (
                (
                    TRY_CAST(s.revenue AS DECIMAL(18,2))
                    - TRY_CAST(s.budget AS DECIMAL(18,2))
                )
                / TRY_CAST(s.budget AS DECIMAL(18,2))
            ) * 100
        ELSE NULL
    END AS ROI_Percent,

    TRY_CAST(s.popularity AS DECIMAL(18,4)),

    TRY_CAST(s.vote_average AS DECIMAL(5,2)),

    TRY_CAST(s.vote_count AS INT),

    s.status,

    s.imdb_id

FROM stg.stg_movies s

LEFT JOIN dim.dim_date d
    ON d.FullDate = TRY_CAST(s.release_date AS DATE)

LEFT JOIN dim.dim_director dr
    ON dr.DirectorName =
       NULLIF(LTRIM(RTRIM(s.directors)), '')

LEFT JOIN dim.dim_writer w
    ON w.WriterName =
       NULLIF(LTRIM(RTRIM(s.writers)), '')

LEFT JOIN dim.dim_production_company pc
    ON pc.ProductionCompanyName =
       NULLIF(LTRIM(RTRIM(s.production_companies)), '')

LEFT JOIN dim.dim_country c
    ON c.CountryName =
       NULLIF(LTRIM(RTRIM(s.production_countries)), '')

LEFT JOIN dim.dim_language l
    ON l.LanguageCode =
       NULLIF(LTRIM(RTRIM(s.original_language)), '')

WHERE NOT EXISTS
(
    SELECT 1
    FROM fact.fact_movie f
    WHERE f.MovieID = s.movie_id
);




-- Validate the fact table

SELECT
    COUNT(*) AS FactMovies,
    COUNT(DISTINCT MovieID) AS UniqueMovies,
    COUNT(DateKey) AS MoviesWithDate,
    COUNT(DirectorKey) AS MoviesWithDirector,
    COUNT(WriterKey) AS MoviesWithWriter,
    COUNT(ProductionCompanyKey) AS MoviesWithCompany,
    COUNT(CountryKey) AS MoviesWithCountry,
    COUNT(LanguageKey) AS MoviesWithLanguage,
    COUNT(Budget) AS MoviesWithBudget,
    COUNT(Revenue) AS MoviesWithRevenue,
    COUNT(Profit) AS MoviesWithProfit
FROM fact.fact_movie;


-- check duplicates

SELECT
    MovieID,
    COUNT(*) AS DuplicateCount
FROM fact.fact_movie
GROUP BY MovieID
HAVING COUNT(*) > 1;


-- Check fact records


SELECT TOP 20
    f.MovieID,
    f.Title,
    d.Year,
    d.FullDate,
    dr.DirectorName,
    w.WriterName,
    pc.ProductionCompanyName,
    c.CountryName,
    l.LanguageCode,
    f.Budget,
    f.Revenue,
    f.Profit,
    f.ROI_Percent,
    f.TMDB_Rating,
    f.TMDB_VoteCount
FROM fact.fact_movie f
LEFT JOIN dim.dim_date d
    ON f.DateKey = d.DateKey
LEFT JOIN dim.dim_director dr
    ON f.DirectorKey = dr.DirectorKey
LEFT JOIN dim.dim_writer w
    ON f.WriterKey = w.WriterKey
LEFT JOIN dim.dim_production_company pc
    ON f.ProductionCompanyKey = pc.ProductionCompanyKey
LEFT JOIN dim.dim_country c
    ON f.CountryKey = c.CountryKey
LEFT JOIN dim.dim_language l
    ON f.LanguageKey = l.LanguageKey
ORDER BY f.MovieID;