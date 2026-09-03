USE CineMetrics;
GO

-- Date


IF OBJECT_ID('dim.dim_date', 'U') IS NOT NULL
    DROP TABLE dim.dim_date;
GO

CREATE TABLE dim.dim_date
(
    DateKey         INT NOT NULL PRIMARY KEY,
    FullDate        DATE NOT NULL UNIQUE,

    Year            INT NOT NULL,
    Quarter         INT NOT NULL,
    QuarterName     VARCHAR(10) NOT NULL,

    Month           INT NOT NULL,
    MonthName       VARCHAR(20) NOT NULL,

    MonthShortName  VARCHAR(10) NOT NULL,

    Day             INT NOT NULL,
    DayOfWeek       INT NOT NULL,
    DayName         VARCHAR(20) NOT NULL,

    IsWeekend       BIT NOT NULL
);
GO


-- Genre


IF OBJECT_ID('dim.dim_genre', 'U') IS NOT NULL
    DROP TABLE dim.dim_genre;
GO

CREATE TABLE dim.dim_genre
(
    GenreKey        INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_genre PRIMARY KEY,

    GenreName       NVARCHAR(100) NOT NULL,

    CONSTRAINT UQ_dim_genre_GenreName
        UNIQUE (GenreName)
);
GO


-- Director

IF OBJECT_ID('dim.dim_director', 'U') IS NOT NULL
    DROP TABLE dim.dim_director;
GO

CREATE TABLE dim.dim_director
(
    DirectorKey     INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_director PRIMARY KEY,

    DirectorName    NVARCHAR(300) NOT NULL,

    CONSTRAINT UQ_dim_director_DirectorName
        UNIQUE (DirectorName)
);
GO


-- Writer

IF OBJECT_ID('dim.dim_writer', 'U') IS NOT NULL
    DROP TABLE dim.dim_writer;
GO

CREATE TABLE dim.dim_writer
(
    WriterKey       INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_writer PRIMARY KEY,

    WriterName      NVARCHAR(300) NOT NULL,

    CONSTRAINT UQ_dim_writer_WriterName
        UNIQUE (WriterName)
);
GO


-- Actors

IF OBJECT_ID('dim.dim_actor', 'U') IS NOT NULL
    DROP TABLE dim.dim_actor;
GO

CREATE TABLE dim.dim_actor
(
    ActorKey        INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_actor PRIMARY KEY,

    ActorName       NVARCHAR(300) NOT NULL,

    CONSTRAINT UQ_dim_actor_ActorName
        UNIQUE (ActorName)
);
GO


-- Production company

IF OBJECT_ID('dim.dim_production_company', 'U') IS NOT NULL
    DROP TABLE dim.dim_production_company;
GO

CREATE TABLE dim.dim_production_company
(
    ProductionCompanyKey INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_production_company PRIMARY KEY,

    ProductionCompanyName NVARCHAR(300) NOT NULL,

    CONSTRAINT UQ_dim_production_company_Name
        UNIQUE (ProductionCompanyName)
);
GO


-- Country

IF OBJECT_ID('dim.dim_country', 'U') IS NOT NULL
    DROP TABLE dim.dim_country;
GO

CREATE TABLE dim.dim_country
(
    CountryKey      INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_country PRIMARY KEY,

    CountryName     NVARCHAR(200) NOT NULL,

    CONSTRAINT UQ_dim_country_Name
        UNIQUE (CountryName)
);
GO


-- Language

IF OBJECT_ID('dim.dim_language', 'U') IS NOT NULL
    DROP TABLE dim.dim_language;
GO

CREATE TABLE dim.dim_language
(
    LanguageKey     INT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_dim_language PRIMARY KEY,

    LanguageCode    VARCHAR(20) NOT NULL,

    CONSTRAINT UQ_dim_language_Code
        UNIQUE (LanguageCode)
);
GO