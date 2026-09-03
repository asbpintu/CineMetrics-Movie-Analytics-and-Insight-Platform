USE CineMetrics;
GO

IF OBJECT_ID('stg.stg_movies', 'U') IS NOT NULL
    DROP TABLE stg.stg_movies;
GO

CREATE TABLE stg.stg_movies
(
    movie_id                    INT NULL,
    title                       NVARCHAR(500) NULL,
    release_date                DATE NULL,

    overview                    NVARCHAR(MAX) NULL,
    tagline                     NVARCHAR(1000) NULL,
    homepage                    NVARCHAR(1000) NULL,

    poster_path                 NVARCHAR(500) NULL,
    backdrop_path               NVARCHAR(500) NULL,

    original_language           VARCHAR(20) NULL,
    genres                      NVARCHAR(2000) NULL,

    popularity                  DECIMAL(18,6) NULL,
    vote_average                DECIMAL(5,2) NULL,
    vote_count                  INT NULL,

    budget                      BIGINT NULL,
    revenue                     BIGINT NULL,
    runtime                     INT NULL,

    production_companies       NVARCHAR(1000) NULL,
    production_countries       NVARCHAR(1000) NULL,

    status                      NVARCHAR(100) NULL,

    imdb_id                     VARCHAR(30) NULL,
    imdb_rating                 DECIMAL(5,2) NULL,
    imdb_votes                  INT NULL,

    directors                   NVARCHAR(500) NULL,
    writers                     NVARCHAR(500) NULL,
    cast_top_5                  NVARCHAR(2000) NULL
);
GO