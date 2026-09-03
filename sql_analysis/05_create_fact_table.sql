USE CineMetrics;
GO

IF OBJECT_ID('fact.fact_movie', 'U') IS NOT NULL
    DROP TABLE fact.fact_movie;
GO

CREATE TABLE fact.fact_movie
(
    MovieID                 INT NOT NULL,

    DateKey                 INT NULL,

    DirectorKey             INT NULL,
    WriterKey               INT NULL,
    ProductionCompanyKey   INT NULL,
    CountryKey              INT NULL,
    LanguageKey             INT NULL,

    Title                   NVARCHAR(500) NULL,

    Overview                NVARCHAR(MAX) NULL,
    Tagline                 NVARCHAR(1000) NULL,
    Homepage                NVARCHAR(1000) NULL,

    PosterPath              NVARCHAR(500) NULL,
    BackdropPath            NVARCHAR(500) NULL,

    RuntimeMinutes          INT NULL,

    Budget                  BIGINT NULL,
    Revenue                 BIGINT NULL,

    Profit                  BIGINT NULL,

    ROI_Percent             DECIMAL(18,2) NULL,

    TMDB_Popularity         DECIMAL(18,6) NULL,
    TMDB_Rating             DECIMAL(5,2) NULL,
    TMDB_VoteCount          INT NULL,

    IMDb_Rating             DECIMAL(5,2) NULL,
    IMDb_VoteCount          INT NULL,

    MovieStatus             NVARCHAR(100) NULL,

    IMDb_ID                 VARCHAR(30) NULL,

    CONSTRAINT PK_fact_movie
        PRIMARY KEY (MovieID),

    CONSTRAINT FK_fact_movie_Date
        FOREIGN KEY (DateKey)
        REFERENCES dim.dim_date(DateKey),

    CONSTRAINT FK_fact_movie_Director
        FOREIGN KEY (DirectorKey)
        REFERENCES dim.dim_director(DirectorKey),

    CONSTRAINT FK_fact_movie_Writer
        FOREIGN KEY (WriterKey)
        REFERENCES dim.dim_writer(WriterKey),

    CONSTRAINT FK_fact_movie_Company
        FOREIGN KEY (ProductionCompanyKey)
        REFERENCES dim.dim_production_company(ProductionCompanyKey),

    CONSTRAINT FK_fact_movie_Country
        FOREIGN KEY (CountryKey)
        REFERENCES dim.dim_country(CountryKey),

    CONSTRAINT FK_fact_movie_Language
        FOREIGN KEY (LanguageKey)
        REFERENCES dim.dim_language(LanguageKey)
);
GO