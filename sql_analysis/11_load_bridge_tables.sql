USE CineMetrics;
GO


-- Movie → Genres


INSERT INTO bridge.bridge_movie_genre
(
    MovieID,
    GenreKey
)
SELECT DISTINCT
    s.movie_id,
    g.GenreKey
FROM stg.stg_movies s
CROSS APPLY STRING_SPLIT(s.genres, '|') ss
INNER JOIN dim.dim_genre g
    ON g.GenreName = LTRIM(RTRIM(ss.value))
WHERE NULLIF(LTRIM(RTRIM(s.genres)), '') IS NOT NULL
  AND NOT EXISTS
  (
      SELECT 1
      FROM bridge.bridge_movie_genre b
      WHERE b.MovieID = s.movie_id
        AND b.GenreKey = g.GenreKey
  );

-- Validations

  SELECT
    COUNT(*) AS TotalGenreLinks,
    COUNT(DISTINCT MovieID) AS MoviesWithGenres,
    COUNT(DISTINCT GenreKey) AS GenresUsed
FROM bridge.bridge_movie_genre;

-- Check records

SELECT TOP 20
    b.MovieID,
    f.Title,
    g.GenreName
FROM bridge.bridge_movie_genre b
INNER JOIN fact.fact_movie f
    ON b.MovieID = f.MovieID
INNER JOIN dim.dim_genre g
    ON b.GenreKey = g.GenreKey
ORDER BY b.MovieID, g.GenreName;





-- Movie → Actor

INSERT INTO bridge.bridge_movie_actor
(
    MovieID,
    ActorKey,
    CastOrder
)
SELECT DISTINCT
    s.movie_id,
    a.ActorKey,
    TRY_CAST(ss.ordinal AS INT) AS CastOrder
FROM stg.stg_movies s
CROSS APPLY STRING_SPLIT(s.cast_top_5, '|', 1) ss
INNER JOIN dim.dim_actor a
    ON a.ActorName = LTRIM(RTRIM(ss.value))
WHERE NULLIF(LTRIM(RTRIM(s.cast_top_5)), '') IS NOT NULL
  AND NOT EXISTS
  (
      SELECT 1
      FROM bridge.bridge_movie_actor b
      WHERE b.MovieID = s.movie_id
        AND b.ActorKey = a.ActorKey
  );


-- Validations

SELECT
    COUNT(*) AS TotalActorLinks,
    COUNT(DISTINCT MovieID) AS MoviesWithActors,
    COUNT(DISTINCT ActorKey) AS ActorsUsed
FROM bridge.bridge_movie_actor;


-- Check records

SELECT TOP 30
    b.MovieID,
    f.Title,
    b.CastOrder,
    a.ActorName
FROM bridge.bridge_movie_actor b
INNER JOIN fact.fact_movie f
    ON b.MovieID = f.MovieID
INNER JOIN dim.dim_actor a
    ON b.ActorKey = a.ActorKey
ORDER BY b.MovieID, b.CastOrder;

-- validate not more than 5 Actors

SELECT
    MovieID,
    COUNT(*) AS ActorCount
FROM bridge.bridge_movie_actor
GROUP BY MovieID
HAVING COUNT(*) > 5;