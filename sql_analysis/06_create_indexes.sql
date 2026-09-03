USE CineMetrics;
GO

CREATE INDEX IX_fact_movie_DateKey
ON fact.fact_movie(DateKey);
GO

CREATE INDEX IX_fact_movie_DirectorKey
ON fact.fact_movie(DirectorKey);
GO

CREATE INDEX IX_fact_movie_WriterKey
ON fact.fact_movie(WriterKey);
GO

CREATE INDEX IX_fact_movie_CompanyKey
ON fact.fact_movie(ProductionCompanyKey);
GO

CREATE INDEX IX_fact_movie_CountryKey
ON fact.fact_movie(CountryKey);
GO

CREATE INDEX IX_fact_movie_LanguageKey
ON fact.fact_movie(LanguageKey);
GO

CREATE INDEX IX_bridge_movie_genre_GenreKey
ON bridge.bridge_movie_genre(GenreKey);
GO

CREATE INDEX IX_bridge_movie_actor_ActorKey
ON bridge.bridge_movie_actor(ActorKey);
GO