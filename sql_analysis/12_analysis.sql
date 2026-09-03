USE CineMetrics;
GO


-- Important Executive KPI Query

SELECT
    COUNT(*) AS TotalMovies,

    SUM(ISNULL(Budget, 0)) AS TotalBudget,

    SUM(ISNULL(Revenue, 0)) AS TotalRevenue,

    SUM(ISNULL(Profit, 0)) AS TotalProfit,

    AVG(TMDB_Rating) AS AverageRating,

    AVG(TMDB_Popularity) AS AveragePopularity,

    SUM(ISNULL(TMDB_VoteCount, 0)) AS TotalVotes,

    AVG(
        CASE
            WHEN Budget > 0
            THEN ROI_Percent
        END
    ) AS AverageROI,

    AVG(RuntimeMinutes) AS AverageRuntime

FROM fact.fact_movie;


-- Most Profitable Movies


SELECT TOP 20
    MovieID,
    Title,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Rating,
    TMDB_Popularity
FROM fact.fact_movie
WHERE Profit IS NOT NULL
ORDER BY Profit DESC;


-- Find Movies That Lost Money

SELECT TOP 50
    MovieID,
    Title,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Rating
FROM fact.fact_movie
WHERE
    Budget > 0
    AND Revenue > 0
    AND Revenue < Budget
ORDER BY Profit ASC;

-- High Rating + High Profit Movies

SELECT TOP 50
    MovieID,
    Title,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Rating,
    TMDB_VoteCount
FROM fact.fact_movie
WHERE
    TMDB_Rating >= 7.5
    AND Profit > 0
ORDER BY Profit DESC;


-- High ROI but Low Budget

SELECT TOP 50
    MovieID,
    Title,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Rating
FROM fact.fact_movie
WHERE
    Budget BETWEEN 1000000 AND 10000000
    AND ROI_Percent IS NOT NULL
ORDER BY ROI_Percent DESC;


-- Big Budget Failures

SELECT TOP 30
    MovieID,
    Title,
    Budget,
    Revenue,
    Profit,
    ROI_Percent,
    TMDB_Rating
FROM fact.fact_movie
WHERE
    Budget >= 100000000
    AND Profit < 0
ORDER BY Profit ASC;


-- Director + Genre Performance

SELECT
    dir.DirectorName,
    g.GenreName,

    COUNT(DISTINCT f.MovieID) AS MovieCount,

    SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,
    SUM(ISNULL(f.Profit, 0)) AS TotalProfit,

    AVG(f.TMDB_Rating) AS AverageRating,

    AVG(
        CASE
            WHEN f.Budget > 0
            THEN f.ROI_Percent
        END
    ) AS AverageROI

FROM fact.fact_movie f

INNER JOIN dim.dim_director dir
    ON f.DirectorKey = dir.DirectorKey

INNER JOIN bridge.bridge_movie_genre bg
    ON f.MovieID = bg.MovieID

INNER JOIN dim.dim_genre g
    ON bg.GenreKey = g.GenreKey

GROUP BY
    dir.DirectorName,
    g.GenreName

HAVING COUNT(DISTINCT f.MovieID) >= 2

ORDER BY TotalRevenue DESC;


-- Actor + Genre Performance

SELECT
    a.ActorName,
    g.GenreName,

    COUNT(DISTINCT f.MovieID) AS MovieCount,

    AVG(f.TMDB_Rating) AS AverageRating,

    SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,

    SUM(ISNULL(f.Profit, 0)) AS TotalProfit

FROM bridge.bridge_movie_actor ba

INNER JOIN dim.dim_actor a
    ON ba.ActorKey = a.ActorKey

INNER JOIN fact.fact_movie f
    ON ba.MovieID = f.MovieID

INNER JOIN bridge.bridge_movie_genre bg
    ON f.MovieID = bg.MovieID

INNER JOIN dim.dim_genre g
    ON bg.GenreKey = g.GenreKey

GROUP BY
    a.ActorName,
    g.GenreName

HAVING COUNT(DISTINCT f.MovieID) >= 2

ORDER BY TotalRevenue DESC;

-- Top-Billed Actor Analysis

SELECT TOP 50
    a.ActorName,

    COUNT(DISTINCT ba.MovieID) AS LeadMovies,

    AVG(f.TMDB_Rating) AS AverageRating,

    SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,

    SUM(ISNULL(f.Profit, 0)) AS TotalProfit,

    AVG(
        CASE
            WHEN f.Budget > 0
            THEN f.ROI_Percent
        END
    ) AS AverageROI

FROM bridge.bridge_movie_actor ba

INNER JOIN dim.dim_actor a
    ON ba.ActorKey = a.ActorKey

INNER JOIN fact.fact_movie f
    ON ba.MovieID = f.MovieID

WHERE ba.CastOrder = 1

GROUP BY
    a.ActorName

HAVING COUNT(DISTINCT ba.MovieID) >= 2

ORDER BY TotalRevenue DESC;


-- Yearly Growth Analysis

WITH yearly AS
(
    SELECT
        d.Year AS ReleaseYear,

        COUNT(*) AS MovieCount,

        SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,

        SUM(ISNULL(f.Profit, 0)) AS TotalProfit

    FROM fact.fact_movie f

    INNER JOIN dim.dim_date d
        ON f.DateKey = d.DateKey

    GROUP BY d.Year
)

SELECT
    ReleaseYear,
    MovieCount,
    TotalRevenue,
    TotalProfit,

    LAG(TotalRevenue) OVER (
        ORDER BY ReleaseYear
    ) AS PreviousYearRevenue,

    (
        TotalRevenue
        -
        LAG(TotalRevenue) OVER (
            ORDER BY ReleaseYear
        )
    ) AS RevenueChange,

    (
        (
            TotalRevenue
            -
            LAG(TotalRevenue) OVER (
                ORDER BY ReleaseYear
            )
        )
        /
        NULLIF(
            LAG(TotalRevenue) OVER (
                ORDER BY ReleaseYear
            ),
            0
        )
    ) * 100 AS RevenueGrowthPct

FROM yearly
ORDER BY ReleaseYear;


-- Genre Ranking Within Each Year

WITH genre_year AS
(
    SELECT
        d.Year AS ReleaseYear,
        g.GenreName,

        COUNT(DISTINCT f.MovieID) AS MovieCount,

        SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,

        SUM(ISNULL(f.Profit, 0)) AS TotalProfit

    FROM bridge.bridge_movie_genre bg

    INNER JOIN fact.fact_movie f
        ON bg.MovieID = f.MovieID

    INNER JOIN dim.dim_genre g
        ON bg.GenreKey = g.GenreKey

    INNER JOIN dim.dim_date d
        ON f.DateKey = d.DateKey

    GROUP BY
        d.Year,
        g.GenreName
)

SELECT
    ReleaseYear,
    GenreName,
    MovieCount,
    TotalRevenue,
    TotalProfit,

    RANK() OVER (
        PARTITION BY ReleaseYear
        ORDER BY TotalRevenue DESC
    ) AS RevenueRank

FROM genre_year

ORDER BY
    ReleaseYear,
    RevenueRank;



-- Top 3 Genres Per Year

WITH genre_year AS
(
    SELECT
        d.Year AS ReleaseYear,
        g.GenreName,

        COUNT(DISTINCT f.MovieID) AS MovieCount,

        SUM(ISNULL(f.Revenue, 0)) AS TotalRevenue,

        SUM(ISNULL(f.Profit, 0)) AS TotalProfit

    FROM bridge.bridge_movie_genre bg

    INNER JOIN fact.fact_movie f
        ON bg.MovieID = f.MovieID

    INNER JOIN dim.dim_genre g
        ON bg.GenreKey = g.GenreKey

    INNER JOIN dim.dim_date d
        ON f.DateKey = d.DateKey

    GROUP BY
        d.Year,
        g.GenreName
),

ranked AS
(
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY ReleaseYear
            ORDER BY TotalRevenue DESC
        ) AS rn
    FROM genre_year
)

SELECT
    ReleaseYear,
    GenreName,
    MovieCount,
    TotalRevenue,
    TotalProfit
FROM ranked
WHERE rn <= 3
ORDER BY
    ReleaseYear,
    rn;

