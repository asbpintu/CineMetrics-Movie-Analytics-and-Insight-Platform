"""Fill missing movie backdrop and poster paths from TMDB.

By default, existing image paths are kept and the results are written to
``data/processed/cinemetrics_movies_2020_2026_with_backdrops.csv``.
Set ``TMDB_READ_ACCESS_TOKEN`` in the project ``.env`` file before running.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "cinemetrics_movies_2020_2026.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "cinemetrics_movies_2020_2026_with_backdrops.csv"
)
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "tmdb_images"
ENV_FILE = PROJECT_ROOT / ".env"
TMDB_MOVIE_URL = "https://api.themoviedb.org/3/movie"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch missing movie backdrop and poster paths from TMDB."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N movies needing an image path.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.1,
        help="Delay between uncached TMDB requests in seconds (default: 0.1).",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Fetch backdrop paths for every movie, including populated rows.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cached TMDB responses.",
    )
    return parser.parse_args()


def load_tmdb_token() -> str:
    load_dotenv(ENV_FILE)
    token = os.getenv("TMDB_READ_ACCESS_TOKEN")
    if not token or not token.strip():
        raise RuntimeError(
            "TMDB_READ_ACCESS_TOKEN was not found. Add it to the project .env file."
        )
    return token.strip()


def create_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CineMetrics-Backdrop-Enrichment/1.0",
        }
    )
    return session


def load_cached_image_paths(
    movie_id: int,
) -> Tuple[bool, Optional[str], Optional[str]]:
    cache_file = CACHE_DIR / f"{movie_id}.json"
    if not cache_file.exists():
        return False, None, None

    with cache_file.open("r", encoding="utf-8") as file:
        cached: Any = json.load(file)
    if not isinstance(cached, dict) or not {
        "backdrop_path",
        "poster_path",
    }.issubset(cached):
        raise ValueError(f"Invalid backdrop cache entry: {cache_file}")

    image_paths = (cached["backdrop_path"], cached["poster_path"])
    if any(path is not None and not isinstance(path, str) for path in image_paths):
        raise ValueError(f"Invalid image paths in cache entry: {cache_file}")
    return True, image_paths[0], image_paths[1]


def save_cached_image_paths(
    movie_id: int,
    backdrop_path: Optional[str],
    poster_path: Optional[str],
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{movie_id}.json"
    temporary_file = cache_file.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "backdrop_path": backdrop_path,
                "poster_path": poster_path,
            },
            file,
        )
    temporary_file.replace(cache_file)


def fetch_image_paths(
    session: requests.Session,
    movie_id: int,
    force_refresh: bool = False,
) -> Tuple[Optional[str], Optional[str], bool]:
    if not force_refresh:
        found, backdrop_path, poster_path = load_cached_image_paths(movie_id)
        if found:
            return backdrop_path, poster_path, True

    url = f"{TMDB_MOVIE_URL}/{movie_id}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(min(30, (2 ** (attempt - 1)) + random.random()))
            continue

        if response.status_code == 404:
            backdrop_path = None
            poster_path = None
            break
        if response.status_code in RETRY_STATUS_CODES:
            if attempt == MAX_RETRIES:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            try:
                wait_time = float(retry_after) if retry_after else 2 ** (attempt - 1)
            except ValueError:
                wait_time = 2 ** (attempt - 1)
            time.sleep(max(0, wait_time) + random.uniform(0, 0.5))
            continue

        response.raise_for_status()
        data: Any = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"TMDB returned an invalid response for movie {movie_id}.")
        image_paths = (data.get("backdrop_path"), data.get("poster_path"))
        if any(path is not None and not isinstance(path, str) for path in image_paths):
            raise ValueError(f"TMDB returned invalid image paths for movie {movie_id}.")
        backdrop_path, poster_path = image_paths
        break
    else:
        raise RuntimeError(f"TMDB request failed after retries for movie {movie_id}.")

    save_cached_image_paths(movie_id, backdrop_path, poster_path)
    return backdrop_path, poster_path, False


def enrich_backdrops(args: argparse.Namespace) -> None:
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be greater than zero.")
    if args.sleep < 0:
        raise ValueError("--sleep must not be negative.")

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    movies = pd.read_csv(input_path, dtype={"movie_id": "string"})
    required_columns = {"movie_id", "backdrop_path", "poster_path"}
    missing_columns = required_columns.difference(movies.columns)
    if missing_columns:
        raise ValueError(f"Input CSV is missing required columns: {sorted(missing_columns)}")

    missing_ids = movies["movie_id"].isna() | movies["movie_id"].str.strip().eq("")
    if missing_ids.any():
        raise ValueError(f"Input CSV contains {int(missing_ids.sum())} missing TMDB movie IDs.")

    if args.refresh_existing:
        row_indices = list(movies.index)
    else:
        image_paths_missing = (
            movies["backdrop_path"].isna()
            | movies["backdrop_path"].astype("string").str.strip().eq("")
            | movies["poster_path"].isna()
            | movies["poster_path"].astype("string").str.strip().eq("")
        )
        row_indices = list(movies.index[image_paths_missing])

    if args.limit is not None:
        row_indices = row_indices[: args.limit]

    token = load_tmdb_token()
    session = create_session(token)
    fetched_count = 0
    cached_count = 0
    no_backdrop_count = 0
    no_poster_count = 0

    print(f"Movies to process: {len(row_indices):,}")
    for position, row_index in enumerate(row_indices, start=1):
        raw_movie_id = movies.at[row_index, "movie_id"].strip()
        try:
            movie_id = int(raw_movie_id)
        except ValueError as exc:
            raise ValueError(
                f"Invalid TMDB movie ID at CSV row {row_index + 2}: {raw_movie_id!r}"
            ) from exc

        backdrop_path, poster_path, was_cached = fetch_image_paths(
            session,
            movie_id,
            force_refresh=args.force_refresh,
        )
        current_backdrop = movies.at[row_index, "backdrop_path"]
        if (
            args.refresh_existing
            or pd.isna(current_backdrop)
            or not str(current_backdrop).strip()
        ):
            movies.at[row_index, "backdrop_path"] = backdrop_path
        current_poster = movies.at[row_index, "poster_path"]
        if (
            args.refresh_existing
            or pd.isna(current_poster)
            or not str(current_poster).strip()
        ):
            movies.at[row_index, "poster_path"] = poster_path
        cached_count += int(was_cached)
        fetched_count += int(not was_cached)
        no_backdrop_count += int(backdrop_path is None)
        no_poster_count += int(poster_path is None)

        print(
            f"[{position:,}/{len(row_indices):,}] "
            f"TMDB {movie_id}: backdrop={backdrop_path or 'none'}, "
            f"poster={poster_path or 'none'}"
            f"{' (cache)' if was_cached else ''}"
        )
        if not was_cached and position < len(row_indices):
            time.sleep(args.sleep)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    movies.to_csv(output_path, index=False)
    print(
        f"Saved {len(movies):,} rows to {output_path}\n"
        f"TMDB requests: {fetched_count:,}; cache hits: {cached_count:,}; "
        f"no backdrop returned: {no_backdrop_count:,}; "
        f"no poster returned: {no_poster_count:,}"
    )


def main() -> None:
    enrich_backdrops(parse_args())


if __name__ == "__main__":
    main()
