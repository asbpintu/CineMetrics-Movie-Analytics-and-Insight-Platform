USE CineMetrics;
GO


-- Movie → Genre

IF OBJECT_ID('bridge.bridge_movie_genre', 'U') IS NOT NULL
    DROP TABLE bridge.bridge_movie_genre;
GO

CREATE TABLE bridge.bridge_movie_genre
(
    MovieID         INT NOT NULL,
    GenreKey        INT NOT NULL,

    CONSTRAINT PK_bridge_movie_genre
        PRIMARY KEY (MovieID, GenreKey),

    CONSTRAINT FK_bridge_movie_genre_Genre
        FOREIGN KEY (GenreKey)
        REFERENCES dim.dim_genre(GenreKey)
);
GO


-- Movie → Actor

IF OBJECT_ID('bridge.bridge_movie_actor', 'U') IS NOT NULL
    DROP TABLE bridge.bridge_movie_actor;
GO

CREATE TABLE bridge.bridge_movie_actor
(
    MovieID         INT NOT NULL,
    ActorKey        INT NOT NULL,

    CastOrder       INT NULL,

    CONSTRAINT PK_bridge_movie_actor
        PRIMARY KEY (MovieID, ActorKey),

    CONSTRAINT FK_bridge_movie_actor_Actor
        FOREIGN KEY (ActorKey)
        REFERENCES dim.dim_actor(ActorKey)
);
GO