USE CineMetrics;
GO

IF OBJECT_ID('stg.stg_movies', 'U') IS NOT NULL
    DROP TABLE stg.stg_movies;
GO

CREATE TABLE stg.stg_movies
(
    backdrop_path           NVARCHAR(500) NULL,
    budget                  BIGINT NULL,
    genres                  NVARCHAR(2000) NULL,
    movie_id                INT NULL,

    original_language       VARCHAR(20) NULL,
    overview                NVARCHAR(MAX) NULL,
    popularity              DECIMAL(18,6) NULL,

    poster_path             NVARCHAR(500) NULL,

    production_companies    NVARCHAR(1000) NULL,
    production_countries    NVARCHAR(1000) NULL,

    release_date            DATE NULL,

    revenue                 BIGINT NULL,
    runtime                 INT NULL,

    status                  NVARCHAR(100) NULL,
    title                   NVARCHAR(500) NULL,

    vote_average            DECIMAL(5,2) NULL,
    vote_count               INT NULL,

    imdb_id                 VARCHAR(30) NULL,

    tagline                 NVARCHAR(1000) NULL,
    homepage                NVARCHAR(1000) NULL,

    directors               NVARCHAR(500) NULL,
    writers                 NVARCHAR(500) NULL,
    cast_top_5              NVARCHAR(2000) NULL
);
GO