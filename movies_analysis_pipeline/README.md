# Movies Analysis Dataset — IMDb + TMDB (2020–2026)

This project builds a reproducible movie dataset for SQL, Power BI and Python.

## Data sources

- IMDb official non-commercial datasets provide the movie IDs, titles, years,
  runtime, genres, IMDb ratings and vote counts.
- TMDB is used to enrich those IMDb movies with TMDB IDs, release dates,
  TMDB ratings/votes, popularity, budget, revenue, genres, directors, cast,
  production countries/companies and overview information.


## Run

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python build_dataset.py
```

The script downloads the current IMDb dumps and creates:

```text
data/movies_2020_2026.csv
```

TMDB responses are cached under:

```text
data/cache/tmdb/
```

This makes subsequent runs much cheaper/faster because already-enriched IMDb
IDs are not requested again.

## Suggested SQL model

Use the final CSV as a staging table first:

`stg_movies`

Then normalize into:

- `dim_movie`
- `dim_genre`
- `bridge_movie_genre`
- `dim_person`
- `bridge_movie_cast`
- `bridge_movie_director`
- `dim_country`
- `bridge_movie_country`
- `fact_movie_performance`

## Suggested Power BI KPIs

- Total Movies
- Average IMDb Rating
- Average TMDB Rating
- Total Box Office Revenue
- Total Budget
- Total Profit
- Average Profit Margin
- Highest Grossing Movie
- Highest Rated Movie
- Movies Released by Year
- Revenue by Genre
- Rating vs Revenue
- Budget vs Revenue
- Top Directors
- Top Production Countries
- IMDb vs TMDB Rating Difference

## Licensing / attribution

IMDb states that its non-commercial datasets are available for personal and
non-commercial use and are refreshed daily. Review IMDb's current terms before
publishing or redistributing the resulting dataset.

Review TMDB's current API terms and attribution requirements before publishing
an application or dataset based on TMDB data.
