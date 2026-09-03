-- Convert companies and countries to Top 1

USE CineMetrics;
GO

-- Keep only the first production company
UPDATE stg.stg_movies
SET production_companies =
    CASE
        WHEN production_companies IS NULL OR LTRIM(RTRIM(production_companies)) = ''
            THEN NULL
        ELSE LTRIM(RTRIM(
            LEFT(
                production_companies,
                CHARINDEX('|', production_companies + '|') - 1
            )
        ))
    END;

-- Keep only the first production country
UPDATE stg.stg_movies
SET production_countries =
    CASE
        WHEN production_countries IS NULL OR LTRIM(RTRIM(production_countries)) = ''
            THEN NULL
        ELSE LTRIM(RTRIM(
            LEFT(
                production_countries,
                CHARINDEX('|', production_countries + '|') - 1
            )
        ))
    END;
GO


___________________________________________

SELECT TOP 20
    movie_id,
    production_companies,
    production_countries
FROM stg.stg_movies
WHERE production_companies LIKE '%|%'
   OR production_countries LIKE '%|%';