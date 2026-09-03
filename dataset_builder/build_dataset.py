"""
CineMetrics - Movie Dataset Builder

Pipeline:
1. Download TMDB Raw Movie Dataset from Zenodo
2. Filter movies from 2020-01-01 through 2025-12-31
3. Fetch 2026 YTD movies from TMDB Discover API
4. Enrich selected movies using TMDB movie details + credits
5. Cache TMDB responses locally
6. Save the final 2020-2026 YTD dataset

Base dataset:
TMDB Raw Movie Dataset (2010-2025) - 17,978 Records
Zenodo: https://zenodo.org/records/21920642
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache" / "tmdb"
OUTPUT_DIR = DATA_DIR / "processed"

RAW_FILE = RAW_DIR / "movies_raw.csv"
OUTPUT_FILE = OUTPUT_DIR / "cinemetrics_movies_2020_2026.csv"

TMDB_BASE_URL = "https://api.themoviedb.org/3"

ZENODO_DOWNLOAD_URL = (
    "https://zenodo.org/records/21920642/files/movies_raw.csv?download=1"
)

START_DATE = "2020-01-01"

# Current date is used automatically.
TODAY = date.today()
END_DATE = TODAY.isoformat()

# Only fetch this many 2026 movies per page.
TMDB_PAGE_SIZE = 20

# Maximum number of 2026 pages.
# 20 x 25 = 500 movies.
MAX_2026_PAGES = 25

# Number of cast members to keep.
TOP_CAST_COUNT = 5

# TMDB genre ID -> genre name mapping used by Discover API.
# The movie details endpoint already returns genre names; this mapping
# is needed for 2026 Discover results, which contain only genre_ids.
TMDB_GENRE_MAP = {
    12: "Adventure",
    14: "Fantasy",
    16: "Animation",
    18: "Drama",
    27: "Horror",
    28: "Action",
    35: "Comedy",
    36: "History",
    37: "Western",
    53: "Thriller",
    80: "Crime",
    99: "Documentary",
    878: "Science Fiction",
    9648: "Mystery",
    10402: "Music",
    10749: "Romance",
    10751: "Family",
    10752: "War",
    10770: "TV Movie",
}

# Columns intentionally excluded from the processed CineMetrics dataset.
DROP_COLUMNS = {
    "adult",
    "original_title",
    "spoken_languages",
    "tmdb_original_title",
    "video",
    "dataset_version",
    "dataset_created_at",
    "collection_id",
    "collection_name",
    "tmdb_status",
    "data_source",
}

# Request timeout.
REQUEST_TIMEOUT = 30

# Delay between TMDB requests.
# This keeps the pipeline conservative with API rate limiting.
REQUEST_DELAY = 0.15


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

TMDB_READ_ACCESS_TOKEN = os.getenv("TMDB_READ_ACCESS_TOKEN")

if not TMDB_READ_ACCESS_TOKEN:
    raise RuntimeError(
        "TMDB_READ_ACCESS_TOKEN was not found in your .env file."
    )


# ============================================================
# DIRECTORIES
# ============================================================

RAW_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "Authorization": f"Bearer {TMDB_READ_ACCESS_TOKEN}",
        "accept": "application/json",
        "User-Agent": "CineMetrics/1.0",
    }
)


# ============================================================
# HELPERS
# ============================================================

def log(message: str) -> None:
    """Print a timestamped pipeline message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def save_json(path: Path, data: dict) -> None:
    """Save JSON data."""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_json(path: Path) -> dict:
    """Load JSON data."""
    return json.loads(path.read_text(encoding="utf-8"))


def tmdb_request(
    endpoint: str,
    params: dict | None = None,
    retries: int = 3,
) -> dict | None:
    """
    Make a TMDB API request with retry handling.
    """

    url = f"{TMDB_BASE_URL}{endpoint}"

    for attempt in range(1, retries + 1):

        try:

            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            # Successful response
            if response.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return response.json()

            # Rate limited
            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After",
                    "2",
                )

                try:
                    wait_seconds = int(retry_after)
                except ValueError:
                    wait_seconds = 2

                log(
                    f"TMDB rate limit reached. "
                    f"Waiting {wait_seconds}s..."
                )

                time.sleep(wait_seconds)
                continue

            # Not found
            if response.status_code == 404:

                log(
                    f"TMDB resource not found: {endpoint}"
                )

                return None

            # Other HTTP error
            log(
                f"TMDB HTTP {response.status_code} "
                f"for {endpoint}"
            )

        except requests.RequestException as exc:

            log(
                f"TMDB request failed "
                f"(attempt {attempt}/{retries}): {exc}"
            )

            if attempt < retries:
                time.sleep(2 * attempt)

    return None


# ============================================================
# STEP 1 - DOWNLOAD ZENODO DATASET
# ============================================================

def download_base_dataset() -> None:
    """
    Download movies_raw.csv from Zenodo.
    """

    if RAW_FILE.exists():

        log(
            f"Base dataset already exists: {RAW_FILE}"
        )

        return

    log("Downloading Zenodo TMDB dataset...")
    log(f"URL: {ZENODO_DOWNLOAD_URL}")

    try:

        with requests.get(
            ZENODO_DOWNLOAD_URL,
            stream=True,
            timeout=REQUEST_TIMEOUT,
        ) as response:

            response.raise_for_status()

            total_size = int(
                response.headers.get(
                    "content-length",
                    0,
                )
            )

            downloaded = 0

            with open(RAW_FILE, "wb") as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if not chunk:
                        continue

                    file.write(chunk)

                    downloaded += len(chunk)

                    if total_size:

                        percent = (
                            downloaded / total_size
                        ) * 100

                        print(
                            f"\rDownloading: "
                            f"{percent:6.2f}%",
                            end="",
                        )

        print()

        log(
            f"Dataset downloaded successfully: "
            f"{RAW_FILE}"
        )

    except requests.RequestException as exc:

        if RAW_FILE.exists():
            RAW_FILE.unlink()

        raise RuntimeError(
            f"Failed to download Zenodo dataset: {exc}"
        ) from exc


# ============================================================
# STEP 2 - LOAD AND CLEAN BASE DATASET
# ============================================================

def load_base_dataset() -> pd.DataFrame:
    """
    Load Zenodo CSV and perform basic cleaning.
    """

    log("Loading base dataset...")

    df = pd.read_csv(
        RAW_FILE,
        low_memory=False,
    )

    log(
        f"Loaded {len(df):,} records."
    )

    log(
        f"Columns found: {list(df.columns)}"
    )

    required_columns = {
        "movie_id",
        "title",
        "release_date",
    }

    missing = required_columns - set(df.columns)

    if missing:

        raise ValueError(
            "Required columns missing from Zenodo dataset: "
            f"{sorted(missing)}"
        )

    # --------------------------------------------------------
    # Normalize release date
    # --------------------------------------------------------

    df["release_date"] = pd.to_datetime(
        df["release_date"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Convert movie ID
    # --------------------------------------------------------

    df["movie_id"] = pd.to_numeric(
        df["movie_id"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "movie_id",
            "release_date",
        ]
    )

    df["movie_id"] = df["movie_id"].astype("int64")

    # --------------------------------------------------------
    # Filter 2020-2025
    # --------------------------------------------------------

    start = pd.Timestamp("2020-01-01")
    end = pd.Timestamp("2025-12-31")

    df = df[
        (df["release_date"] >= start)
        & (df["release_date"] <= end)
    ].copy()

    # --------------------------------------------------------
    # Remove duplicate TMDB movie IDs
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["movie_id"],
        keep="first",
    )

    df = df.reset_index(drop=True)

    log(
        f"2020-2025 records after filtering: "
        f"{len(df):,}"
    )

    return df


# ============================================================
# STEP 3 - FETCH 2026 MOVIES FROM TMDB
# ============================================================

def fetch_2026_movies() -> pd.DataFrame:
    """
    Fetch 2026 YTD movies directly from TMDB Discover API.

    This avoids searching movie-by-movie.
    """

    log(
        f"Fetching 2026 YTD movies from TMDB "
        f"({START_DATE} -> {END_DATE})..."
    )

    movies = []

    for page in range(1, MAX_2026_PAGES + 1):

        log(
            f"Fetching TMDB 2026 page "
            f"{page}/{MAX_2026_PAGES}..."
        )

        data = tmdb_request(
            "/discover/movie",
            params={
                "language": "en-US",
                "sort_by": "popularity.desc",
                "include_adult": "false",
                "include_video": "false",
                "page": page,
                "primary_release_date.gte": START_DATE,
                "primary_release_date.lte": END_DATE,
            },
        )

        if not data:
            break

        results = data.get("results", [])

        if not results:
            break

        movies.extend(results)

        total_pages = data.get(
            "total_pages",
            page,
        )

        if page >= total_pages:
            break

        if page >= MAX_2026_PAGES:
            break

    if not movies:

        log("No 2026 movies were returned by TMDB.")

        return pd.DataFrame()

    df = pd.DataFrame(movies)

    # Rename TMDB ID to match Zenodo
    df = df.rename(
        columns={
            "id": "movie_id",
        }
    )

    # Keep only relevant columns
    columns = [
        "movie_id",
        "title",
        "original_title",
        "overview",
        "release_date",
        "original_language",
        "genre_ids",
        "popularity",
        "vote_average",
        "vote_count",
        "poster_path",
        "backdrop_path",
        "adult",
        "video",
    ]

    available = [
        col for col in columns
        if col in df.columns
    ]

    df = df[available].copy()

    # Convert types
    df["movie_id"] = pd.to_numeric(
        df["movie_id"],
        errors="coerce",
    )

    df["release_date"] = pd.to_datetime(
        df["release_date"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "movie_id",
            "release_date",
        ]
    )

    df["movie_id"] = df["movie_id"].astype("int64")

    # Remove duplicates
    df = df.drop_duplicates(
        subset=["movie_id"],
        keep="first",
    )

    df = df.reset_index(drop=True)

    log(
        f"2026 YTD movies fetched: "
        f"{len(df):,}"
    )

    return df


# ============================================================
# STEP 4 - TMDB DETAIL + CREDITS ENRICHMENT
# ============================================================

def get_cache_file(movie_id: int) -> Path:
    """Return cache path for a TMDB movie."""
    return CACHE_DIR / f"{movie_id}.json"


def fetch_movie_details(movie_id: int) -> dict | None:
    """
    Fetch movie details + credits in ONE TMDB request.

    Example endpoint:
    /movie/{movie_id}?append_to_response=credits
    """

    cache_file = get_cache_file(movie_id)

    # --------------------------------------------------------
    # Use cached result if available
    # --------------------------------------------------------

    if cache_file.exists():

        try:
            return load_json(cache_file)

        except Exception:
            log(
                f"Invalid cache file: "
                f"{cache_file}"
            )

    # --------------------------------------------------------
    # Request details + credits
    # --------------------------------------------------------

    data = tmdb_request(
        f"/movie/{movie_id}",
        params={
            "language": "en-US",
            "append_to_response": "credits",
        },
    )

    if data:

        save_json(
            cache_file,
            data,
        )

    return data


def extract_genres(data: dict) -> str:
    """Extract human-readable TMDB genre names."""

    genres = data.get("genres", [])

    names = [
        genre.get("name")
        for genre in genres
        if genre.get("name")
    ]

    return "|".join(dict.fromkeys(names))


def extract_directors(
    credits: dict,
) -> str:
    """Extract the top director."""

    crew = credits.get("crew", [])

    for person in crew:
        if person.get("job") == "Director" and person.get("name"):
            return person["name"]

    return ""


def extract_writers(
    credits: dict,
) -> str:
    """Extract the top writer."""

    crew = credits.get("crew", [])

    writer_jobs = {
        "Writer",
        "Screenplay",
        "Story",
        "Novel",
    }

    for person in crew:
        if (
            person.get("job") in writer_jobs
            and person.get("name")
        ):
            return person["name"]

    return ""


def extract_cast(
    credits: dict,
) -> str:
    """Extract the top 5 cast members."""

    cast = credits.get("cast", [])

    names = [
        person.get("name")
        for person in cast[:TOP_CAST_COUNT]
        if person.get("name")
    ]

    return "|".join(names)


def extract_production_companies(data: dict) -> str:
    """Extract the top production company."""

    companies = data.get("production_companies", [])

    for company in companies:
        if company.get("name"):
            return company["name"]

    return ""


def extract_production_countries(data: dict) -> str:
    """Extract the top production country."""

    countries = data.get("production_countries", [])

    for country in countries:
        name = country.get("name")
        if name:
            return name

    return ""

def enrich_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add selected TMDB enrichment fields.

    Enrichment is cached locally.
    """

    log(
        f"Starting TMDB enrichment for "
        f"{len(df):,} movies..."
    )

    enrichment = []

    total = len(df)

    for index, movie_id in enumerate(
        df["movie_id"],
        start=1,
    ):

        movie_id = int(movie_id)

        # Print progress every movie
        print(
            f"\rTMDB enrichment: "
            f"{index:,}/{total:,} "
            f"({index / total * 100:6.2f}%)",
            end="",
        )

        data = fetch_movie_details(
            movie_id
        )

        if not data:

            enrichment.append(
                {
                    "movie_id": movie_id,
                    "tmdb_status": "not_found",
                }
            )

            continue

        credits = data.get(
            "credits",
            {},
        )

        enrichment.append(
            {
                "movie_id": movie_id,

                # Identity
                "tmdb_original_title":
                    data.get(
                        "original_title"
                    ),

                "imdb_id":
                    data.get(
                        "imdb_id"
                    ),

                # Content
                "overview":
                    data.get(
                        "overview"
                    ),

                # Genres - TMDB details returns human-readable names.
                "tmdb_genres": extract_genres(data),

                "tagline":
                    data.get(
                        "tagline"
                    ),

                # Web / Media
                "homepage":
                    data.get(
                        "homepage"
                    ),

                "poster_path":
                    data.get(
                        "poster_path"
                    ),

                "backdrop_path":
                    data.get(
                        "backdrop_path"
                    ),

                # People
                "directors":
                    extract_directors(
                        credits
                    ),

                "writers":
                    extract_writers(
                        credits
                    ),

                "cast_top_5":
                    extract_cast(
                        credits
                    ),

                # Production - top 1 only.
                "production_companies":
                    extract_production_companies(data),

                "production_countries":
                    extract_production_countries(data),

                "tmdb_status":
                    "success",
            }
        )

    print()

    enrichment_df = pd.DataFrame(
        enrichment
    )

    df = df.merge(
        enrichment_df,
        on="movie_id",
        how="left",
    )

    log("TMDB enrichment completed.")

    return df


# ============================================================
# STEP 5 - STANDARDIZE 2026 DATASET
# ============================================================

def prepare_2026_dataset(
    df_2026: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert TMDB Discover data into a structure
    compatible with the Zenodo dataset.
    """

    if df_2026.empty:
        return df_2026

    df = df_2026.copy()

    # --------------------------------------------------------
    # Convert genre IDs into a string
    # --------------------------------------------------------

    if "genre_ids" in df.columns:

        df["genres"] = df["genre_ids"].apply(
            lambda values: (
                "|".join(
                    TMDB_GENRE_MAP.get(
                        value,
                        f"Unknown ({value})",
                    )
                    for value in values
                )
                if isinstance(values, list)
                else ""
            )
        )

        df = df.drop(
            columns=["genre_ids"]
        )

    # --------------------------------------------------------
    # Add fields existing in the base dataset
    # --------------------------------------------------------

    default_columns = {
        "status": "Released",
        "budget": 0,
        "revenue": 0,
        "runtime": 0,
        "production_companies": "",
        "production_countries": "",
    }

    for column, default in default_columns.items():

        if column not in df.columns:

            df[column] = default

    # --------------------------------------------------------
    # Keep source marker
    # --------------------------------------------------------

    df["data_source"] = "TMDB_2026"

    return df


# ============================================================
# STEP 6 - ADD SOURCE + DATE FIELDS
# ============================================================

def finalize_dataset(
    df_2020_2025: pd.DataFrame,
    df_2026: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine 2020-2025 Zenodo data with 2026 TMDB data.
    """

    base = df_2020_2025.copy()

    base["data_source"] = "Zenodo_TMDB_Raw"

    # --------------------------------------------------------
    # Normalize 2026
    # --------------------------------------------------------

    current_2026 = prepare_2026_dataset(
        df_2026
    )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    if not current_2026.empty:

        # Make sure both datasets have
        # the same columns.

        all_columns = sorted(
            set(base.columns)
            | set(current_2026.columns)
        )

        base = base.reindex(
            columns=all_columns
        )

        current_2026 = current_2026.reindex(
            columns=all_columns
        )

        final_df = pd.concat(
            [
                base,
                current_2026,
            ],
            ignore_index=True,
        )

    else:

        final_df = base

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    final_df = final_df.drop_duplicates(
        subset=["movie_id"],
        keep="first",
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    final_df = final_df.sort_values(
        by=[
            "release_date",
            "popularity",
        ],
        ascending=[
            False,
            False,
        ],
        na_position="last",
    )

    final_df = final_df.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Convert dates to YYYY-MM-DD
    # --------------------------------------------------------

    if "release_date" in final_df.columns:

        final_df["release_date"] = pd.to_datetime(
            final_df["release_date"],
            errors="coerce",
        ).dt.strftime(
            "%Y-%m-%d"
        )

    return final_df


# ============================================================
# STEP 7 - SAVE DATASET
# ============================================================

def save_final_dataset(
    df: pd.DataFrame,
) -> None:
    """Save final CSV."""

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    log(
        f"Final dataset saved:"
    )

    log(
        str(OUTPUT_FILE)
    )

    log(
        f"Final records: {len(df):,}"
    )

    log(
        f"Final columns: {len(df.columns)}"
    )


# ============================================================
# STEP 8 - DATASET SUMMARY
# ============================================================

def print_summary(
    df: pd.DataFrame,
) -> None:
    """Print useful dataset information."""

    print()
    print("=" * 70)
    print("CINEMETRICS DATASET SUMMARY")
    print("=" * 70)

    print(
        f"Records       : {len(df):,}"
    )

    print(
        f"Columns       : {len(df.columns):,}"
    )

    if "release_date" in df.columns:

        dates = pd.to_datetime(
            df["release_date"],
            errors="coerce",
        )

        print(
            f"Min release   : {dates.min()}"
        )

        print(
            f"Max release   : {dates.max()}"
        )

    if "data_source" in df.columns:

        print()
        print("Data sources:")

        print(
            df["data_source"]
            .value_counts(dropna=False)
            .to_string()
        )

    if "original_language" in df.columns:

        print()
        print("Top languages:")

        print(
            df["original_language"]
            .value_counts()
            .head(10)
            .to_string()
        )

    if "imdb_id" in df.columns:

        imdb_count = (
            df["imdb_id"]
            .notna()
            .sum()
        )

        print()
        print(
            f"Movies with IMDb ID: "
            f"{imdb_count:,}"
        )

    if "directors" in df.columns:

        director_count = (
            df["directors"]
            .fillna("")
            .astype(str)
            .ne("")
            .sum()
        )

        print(
            f"Movies with director data: "
            f"{director_count:,}"
        )

    print("=" * 70)


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:

    start_time = time.time()

    log("=" * 70)
    log("CineMetrics Movie Dataset Pipeline")
    log("=" * 70)

    log(
        f"Project root: {PROJECT_ROOT}"
    )

    log(
        f"Target period: "
        f"{START_DATE} -> {END_DATE}"
    )

    # --------------------------------------------------------
    # 1. Download base dataset
    # --------------------------------------------------------

    download_base_dataset()

    # --------------------------------------------------------
    # 2. Load + filter 2020-2025
    # --------------------------------------------------------

    base_df = load_base_dataset()

    # --------------------------------------------------------
    # 3. Fetch 2026 YTD
    # --------------------------------------------------------

    movies_2026_df = fetch_2026_movies()

    # --------------------------------------------------------
    # 4. Combine before enrichment
    # --------------------------------------------------------

    if not movies_2026_df.empty:

        movies_2026_df = prepare_2026_dataset(
            movies_2026_df
        )

        all_movies = pd.concat(
            [
                base_df,
                movies_2026_df,
            ],
            ignore_index=True,
        )

        all_movies = all_movies.drop_duplicates(
            subset=["movie_id"],
            keep="first",
        )

    else:

        all_movies = base_df.copy()

    # --------------------------------------------------------
    # 5. TMDB enrichment
    # --------------------------------------------------------

    all_movies = enrich_dataframe(
        all_movies
    )

    # --------------------------------------------------------
    # 6. Finalize
    # --------------------------------------------------------

    final_df = finalize_dataset(
        base_df,
        movies_2026_df,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # finalize_dataset currently combines the base and
    # 2026 datasets, so apply enrichment from all_movies.
    # --------------------------------------------------------

    enrichment_columns = [
        "movie_id",
        "tmdb_original_title",
        "imdb_id",
        "overview",
        "tagline",
        "homepage",
        "poster_path",
        "backdrop_path",
        "collection_id",
        "collection_name",
        "directors",
        "writers",
        "cast_top_5",
        "production_companies",
        "production_countries",
        "tmdb_genres",
        "tmdb_status",
    ]

    available_enrichment = [
        col
        for col in enrichment_columns
        if col in all_movies.columns
    ]

    enrichment_only = all_movies[
        available_enrichment
    ].copy()

    # Remove potentially existing enrichment columns
    # before merging again.

    final_df = final_df.drop(
        columns=[
            col
            for col in available_enrichment
            if col != "movie_id"
            and col in final_df.columns
        ],
        errors="ignore",
    )

    final_df = final_df.merge(
        enrichment_only,
        on="movie_id",
        how="left",
    )

    # --------------------------------------------------------
    # Final data-quality cleanup
    # --------------------------------------------------------

    # Keep Zenodo genres as the primary genre field for 2020-2025.
    # For 2026, genres were converted from TMDB genre IDs to names.
    # Where TMDB details contain genres, use those human-readable names.
    if "tmdb_genres" in final_df.columns:
        tmdb_genres = (
            final_df["tmdb_genres"]
            .fillna("")
            .astype(str)
        )

        if "genres" in final_df.columns:
            final_df["genres"] = tmdb_genres.where(
                tmdb_genres.ne(""),
                final_df["genres"],
            )
        else:
            final_df["genres"] = tmdb_genres

    # Remove columns that are not required for CineMetrics analysis.
    final_df = final_df.drop(
        columns=[
            column
            for column in DROP_COLUMNS
            if column in final_df.columns
        ],
        errors="ignore",
    )

    # tmdb_genres was used to standardize the final genres field.
    final_df = final_df.drop(
        columns=["tmdb_genres"],
        errors="ignore",
    )

    # Backward compatibility if an older intermediate column exists.
    if "cast_top_10" in final_df.columns:
        final_df = final_df.rename(
            columns={"cast_top_10": "cast_top_5"}
        )

    # --------------------------------------------------------
    # 7. Save
    # --------------------------------------------------------

    save_final_dataset(
        final_df
    )

    # --------------------------------------------------------
    # 8. Summary
    # --------------------------------------------------------

    print_summary(
        final_df
    )

    elapsed = time.time() - start_time

    print()
    log(
        f"Pipeline completed in "
        f"{elapsed / 60:.2f} minutes."
    )

    log(
        "CineMetrics dataset is ready."
    )


if __name__ == "__main__":
    main()
