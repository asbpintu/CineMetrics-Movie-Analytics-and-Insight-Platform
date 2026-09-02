"""
Build a portfolio-grade movie dataset for 2020-2026.

Sources:
1. IMDb official non-commercial datasets:
   - title.basics.tsv.gz
   - title.ratings.tsv.gz
2. TMDB API:
   - /find/{imdb_id}?external_source=imdb_id
   - /movie/{tmdb_id}
   - /movie/{tmdb_id}/credits

The final CSV keeps both imdb_id and tmdb_id.

Requirements:
    pip install -r requirements.txt

Set TMDB_READ_ACCESS_TOKEN in .env, then:
    python build_dataset.py

The script downloads the current IMDb dumps automatically.
TMDB enrichment is cached in data/cache/tmdb so reruns do not repeatedly
request already-processed movies.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm


START_YEAR = 2020
END_YEAR = 2026

BASE_URL = "https://datasets.imdbws.com"
TMDB_BASE = "https://api.themoviedb.org/3"

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache" / "tmdb"
OUTPUT = DATA / "movies_2020_2026.csv"

RAW.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")
TOKEN = os.getenv("TMDB_READ_ACCESS_TOKEN")

if not TOKEN:
    raise SystemExit(
        "TMDB_READ_ACCESS_TOKEN is missing. Create .env from .env.example "
        "and add your TMDB API Read Access Token."
    )

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "accept": "application/json",
}


def download(url: str, destination: Path) -> None:
    if destination.exists():
        print(f"[SKIP] {destination.name} already exists")
        return

    print(f"[DOWNLOAD] {url}")

    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(30, 120),
            ) as response:
                response.raise_for_status()

                total = int(
                    response.headers.get("content-length", 0)
                )

                with destination.open("wb") as f:
                    with tqdm(
                        total=total,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=destination.name,
                    ) as progress:

                        for chunk in response.iter_content(
                            chunk_size=1024 * 1024
                        ):
                            if chunk:
                                f.write(chunk)
                                progress.update(len(chunk))

            print(f"[DONE] {destination.name}")
            return

        except requests.RequestException as exc:
            print(
                f"[WARN] Download attempt "
                f"{attempt}/{max_attempts} failed: {exc}"
            )

            # Remove incomplete file before retrying.
            if destination.exists():
                destination.unlink()

            if attempt < max_attempts:
                wait = attempt * 3
                print(f"[RETRY] Waiting {wait} seconds...")
                time.sleep(wait)

    raise RuntimeError(
        f"Failed to download {url} after {max_attempts} attempts."
    )


def load_imdb_movies() -> pd.DataFrame:
    basics_path = RAW / "title.basics.tsv.gz"
    ratings_path = RAW / "title.ratings.tsv.gz"

    download(f"{BASE_URL}/title.basics.tsv.gz", basics_path)
    download(f"{BASE_URL}/title.ratings.tsv.gz", ratings_path)

    # Read only columns needed for the core movie table.
    basics = pd.read_csv(
        basics_path,
        sep="\t",
        compression="gzip",
        na_values=r"\N",
        usecols=[
            "tconst",
            "titleType",
            "primaryTitle",
            "originalTitle",
            "isAdult",
            "startYear",
            "runtimeMinutes",
            "genres",
        ],
        dtype={
            "tconst": "string",
            "titleType": "string",
            "primaryTitle": "string",
            "originalTitle": "string",
            "isAdult": "Int8",
            "startYear": "Int16",
            "runtimeMinutes": "Int16",
            "genres": "string",
        },
        engine="python",
    )

    movies = basics[
        (basics["titleType"] == "movie")
        & (basics["startYear"].between(START_YEAR, END_YEAR))
        & (basics["isAdult"] == 0)
    ].copy()

    ratings = pd.read_csv(
        ratings_path,
        sep="\t",
        compression="gzip",
        na_values=r"\N",
        dtype={
            "tconst": "string",
            "averageRating": "float32",
            "numVotes": "Int32",
        },
        engine="python",
    )

    movies = movies.merge(ratings, on="tconst", how="left")

    movies.rename(
        columns={
            "tconst": "imdb_id",
            "primaryTitle": "title",
            "originalTitle": "original_title",
            "startYear": "release_year",
            "runtimeMinutes": "runtime_minutes",
            "averageRating": "imdb_rating",
            "numVotes": "imdb_votes",
        },
        inplace=True,
    )

    movies["release_year"] = movies["release_year"].astype("Int16")
    movies["release_date"] = pd.to_datetime(
        movies["release_year"].astype(str) + "-01-01",
        errors="coerce",
    )

    return movies[
        [
            "imdb_id",
            "title",
            "original_title",
            "release_date",
            "release_year",
            "runtime_minutes",
            "genres",
            "imdb_rating",
            "imdb_votes",
        ]
    ].reset_index(drop=True)


def tmdb_get(path: str, params: dict | None = None) -> dict:
    url = f"{TMDB_BASE}{path}"
    for attempt in range(5):
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=60,
        )

        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", "2"))
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"TMDB rate limit persisted for {path}")


def cache_path(imdb_id: str) -> Path:
    return CACHE / f"{imdb_id}.json"


def enrich_movie(imdb_id: str) -> dict:
    path = cache_path(imdb_id)

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    # TMDB explicitly supports finding movies using IMDb IDs.
    found = tmdb_get(
        f"/find/{imdb_id}",
        params={
            "external_source": "imdb_id",
            "language": "en-US",
        },
    )

    results = found.get("movie_results", [])
    if not results:
        result = {"imdb_id": imdb_id, "tmdb_id": None}
        path.write_text(json.dumps(result), encoding="utf-8")
        return result

    tmdb_id = results[0]["id"]

    details = tmdb_get(
        f"/movie/{tmdb_id}",
        params={"language": "en-US"},
    )

    credits = tmdb_get(
        f"/movie/{tmdb_id}/credits",
        params={"language": "en-US"},
    )

    directors = [
        p["name"]
        for p in credits.get("crew", [])
        if p.get("job") == "Director"
    ]

    cast = [
        p["name"]
        for p in credits.get("cast", [])[:10]
    ]

    countries = [
        c.get("name")
        for c in details.get("production_countries", [])
        if c.get("name")
    ]

    companies = [
        c.get("name")
        for c in details.get("production_companies", [])
        if c.get("name")
    ]

    genres = [
        g.get("name")
        for g in details.get("genres", [])
        if g.get("name")
    ]

    result = {
        "imdb_id": imdb_id,
        "tmdb_id": tmdb_id,
        "tmdb_title": details.get("title"),
        "tmdb_original_title": details.get("original_title"),
        "tmdb_release_date": details.get("release_date"),
        "tmdb_runtime_minutes": details.get("runtime"),
        "tmdb_rating": details.get("vote_average"),
        "tmdb_votes": details.get("vote_count"),
        "tmdb_popularity": details.get("popularity"),
        "budget_usd": details.get("budget"),
        "revenue_usd": details.get("revenue"),
        "profit_usd": (
            details.get("revenue", 0) - details.get("budget", 0)
            if details.get("revenue") is not None
            and details.get("budget") is not None
            and details.get("revenue", 0) > 0
            and details.get("budget", 0) > 0
            else None
        ),
        "original_language": details.get("original_language"),
        "status": details.get("status"),
        "tagline": details.get("tagline"),
        "overview": details.get("overview"),
        "tmdb_genres": "|".join(genres),
        "directors": "|".join(directors),
        "cast": "|".join(cast),
        "production_countries": "|".join(countries),
        "production_companies": "|".join(companies),
        "poster_path": details.get("poster_path"),
        "backdrop_path": details.get("backdrop_path"),
    }

    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    print("Loading IMDb data...")
    imdb = load_imdb_movies()
    print(f"IMDb movies in {START_YEAR}-{END_YEAR}: {len(imdb):,}")

    records = []
    for imdb_id in tqdm(imdb["imdb_id"].dropna(), desc="TMDB enrichment"):
        try:
            records.append(enrich_movie(imdb_id))
        except Exception as exc:
            print(f"[WARN] {imdb_id}: {exc}")
            records.append({"imdb_id": imdb_id, "tmdb_id": None})

    tmdb = pd.DataFrame(records)

    final = imdb.merge(tmdb, on="imdb_id", how="left")

    # Prefer TMDB's actual release date where available.
    final["release_date"] = pd.to_datetime(
        final["tmdb_release_date"]
    ).fillna(final["release_date"])

    final["release_year"] = final["release_date"].dt.year.astype("Int16")

    # Avoid duplicate/conflicting fields.
    final.drop(
        columns=["tmdb_release_date"],
        inplace=True,
        errors="ignore",
    )

    # Useful analytical field.
    final["profit_margin_pct"] = (
        final["profit_usd"] / final["budget_usd"] * 100
    ).where(
        (final["budget_usd"] > 0) & final["profit_usd"].notna()
    )

    final.sort_values(
        ["release_date", "imdb_votes"],
        ascending=[True, False],
        inplace=True,
    )

    final.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    matched = final["tmdb_id"].notna().sum()
    print("\nDONE")
    print(f"Output: {OUTPUT}")
    print(f"Rows: {len(final):,}")
    print(f"IMDb → TMDB matched: {matched:,} ({matched / len(final) * 100:.1f}%)")


if __name__ == "__main__":
    main()
