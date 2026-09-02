from pathlib import Path
import ast
import json

import pandas as pd


# ============================================================
# Configuration
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"

INPUT_FILE = RAW / "new_movies_full.csv"
OUTPUT_FILE = DATA / "movies_2020_2026.csv"

START_YEAR = 2020
END_YEAR = 2026


# ============================================================
# Utility Functions
# ============================================================

def parse_json_column(value):
    """
    Convert JSON-like string columns into Python objects.

    Handles:
    - JSON strings
    - Python-style strings
    - NaN
    - Already parsed objects
    """

    if pd.isna(value):
        return None

    if isinstance(value, (list, dict)):
        return value

    value = str(value).strip()

    if not value:
        return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):

        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None


def extract_names(value):
    """
    Extract 'name' values from nested TMDB JSON.
    """

    parsed = parse_json_column(value)

    if not isinstance(parsed, list):
        return None

    names = []

    for item in parsed:
        if isinstance(item, dict):
            name = item.get("name")

            if name:
                names.append(str(name))

    return ", ".join(names) if names else None


def extract_genres(value):
    """
    Extract genre names.
    """

    return extract_names(value)


def extract_first_name(value):
    """
    Extract the first name from a TMDB list.
    """

    parsed = parse_json_column(value)

    if not isinstance(parsed, list):
        return None

    for item in parsed:
        if isinstance(item, dict):

            name = item.get("name")

            if name:
                return str(name)

    return None


# ============================================================
# Load Dataset
# ============================================================

def load_dataset() -> pd.DataFrame:

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input dataset not found:\n{INPUT_FILE}\n\n"
            "Run download_tmdb_dataset.py first."
        )

    print("=" * 70)
    print("Loading TMDB Dataset")
    print("=" * 70)

    df = pd.read_csv(
        INPUT_FILE,
        low_memory=False,
    )

    print(f"\nRows loaded    : {len(df):,}")
    print(f"Columns loaded : {len(df.columns)}")

    print("\nColumns:")
    for column in df.columns:
        print(f"  - {column}")

    return df


# ============================================================
# Clean Dataset
# ============================================================

def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 70)
    print("Cleaning Dataset")
    print("=" * 70)

    df = df.copy()

    # --------------------------------------------------------
    # Normalize column names
    # --------------------------------------------------------

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # --------------------------------------------------------
    # Release date
    # --------------------------------------------------------

    if "release_date" in df.columns:

        df["release_date"] = pd.to_datetime(
            df["release_date"],
            errors="coerce",
        )

        df["release_year"] = (
            df["release_date"]
            .dt.year
        )

    else:

        raise KeyError(
            "release_date column was not found."
        )

    # --------------------------------------------------------
    # Filter years
    # --------------------------------------------------------

    df = df[
        df["release_year"].between(
            START_YEAR,
            END_YEAR,
        )
    ].copy()

    print(
        f"\nMovies from {START_YEAR}-{END_YEAR}: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Remove duplicate movies
    # --------------------------------------------------------

    if "id" in df.columns:

        before = len(df)

        df = df.drop_duplicates(
            subset=["id"],
            keep="first",
        )

        removed = before - len(df)

        print(
            f"Duplicate movies removed: {removed:,}"
        )

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_columns = [
        "id",
        "runtime",
        "popularity",
        "vote_average",
        "vote_count",
        "budget",
        "revenue",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # Handle invalid runtime
    # --------------------------------------------------------

    if "runtime" in df.columns:

        df.loc[
            df["runtime"] <= 0,
            "runtime"
        ] = pd.NA

    # --------------------------------------------------------
    # Handle invalid financial values
    # --------------------------------------------------------

    for column in ["budget", "revenue"]:

        if column in df.columns:

            df.loc[
                df[column] < 0,
                column
            ] = pd.NA

    return df


# ============================================================
# Feature Engineering
# ============================================================

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:

    print("\n" + "=" * 70)
    print("Feature Engineering")
    print("=" * 70)

    df = df.copy()

    # --------------------------------------------------------
    # ROI
    # --------------------------------------------------------

    if {
        "budget",
        "revenue",
    }.issubset(df.columns):

        df["roi"] = pd.NA

        valid_budget = (
            df["budget"].notna()
            & (df["budget"] > 0)
            & df["revenue"].notna()
        )

        df.loc[
            valid_budget,
            "roi"
        ] = (
            (
                df.loc[valid_budget, "revenue"]
                - df.loc[valid_budget, "budget"]
            )
            / df.loc[valid_budget, "budget"]
        )

    # --------------------------------------------------------
    # Profit
    # --------------------------------------------------------

    if {
        "budget",
        "revenue",
    }.issubset(df.columns):

        df["profit"] = pd.NA

        valid_financials = (
            df["budget"].notna()
            & df["revenue"].notna()
        )

        df.loc[
            valid_financials,
            "profit"
        ] = (
            df.loc[valid_financials, "revenue"]
            - df.loc[valid_financials, "budget"]
        )

    # --------------------------------------------------------
    # Rating category
    # --------------------------------------------------------

    if "vote_average" in df.columns:

        df["rating_category"] = pd.cut(
            df["vote_average"],
            bins=[
                -float("inf"),
                5,
                6,
                7,
                8,
                float("inf"),
            ],
            labels=[
                "Poor",
                "Average",
                "Good",
                "Very Good",
                "Excellent",
            ],
        )

    # --------------------------------------------------------
    # Popularity category
    # --------------------------------------------------------

    if "popularity" in df.columns:

        df["popularity_category"] = pd.qcut(
            df["popularity"],
            q=4,
            labels=[
                "Low",
                "Medium",
                "High",
                "Very High",
            ],
            duplicates="drop",
        )

    # --------------------------------------------------------
    # Decade
    # --------------------------------------------------------

    df["decade"] = (
        (df["release_year"] // 10) * 10
    )

    return df


# ============================================================
# Select Final Columns
# ============================================================

def prepare_final_dataset(
    df: pd.DataFrame,
) -> pd.DataFrame:

    print("\n" + "=" * 70)
    print("Preparing Final Dataset")
    print("=" * 70)

    # --------------------------------------------------------
    # Extract nested TMDB fields
    # --------------------------------------------------------

    if "genres" in df.columns:

        df["genres_clean"] = df["genres"].apply(
            extract_genres
        )

    if "production_companies" in df.columns:

        df["production_companies_clean"] = (
            df["production_companies"].apply(
                extract_names
            )
        )

    if "production_countries" in df.columns:

        df["production_countries_clean"] = (
            df["production_countries"].apply(
                extract_names
            )
        )

    if "spoken_languages" in df.columns:

        df["spoken_languages_clean"] = (
            df["spoken_languages"].apply(
                extract_names
            )
        )

    # --------------------------------------------------------
    # Keep useful analytical fields
    # --------------------------------------------------------

    preferred_columns = [
        "id",
        "title",
        "release_date",
        "release_year",

        "original_language",

        "runtime",

        "genres_clean",

        "overview",

        "tagline",

        "popularity",
        "vote_average",
        "vote_count",

        "budget",
        "revenue",

        "profit",
        "roi",

        "rating_category",
        "popularity_category",

        "production_companies_clean",
        "production_countries_clean",
        "spoken_languages_clean",

        "poster_path",
        "backdrop_path",

        "homepage",

        "status",

        "decade",
    ]

    final_columns = [
        column
        for column in preferred_columns
        if column in df.columns
    ]

    df = df[final_columns].copy()

    # --------------------------------------------------------
    # Rename columns for CineMetrics
    # --------------------------------------------------------

    rename_map = {
        "id": "tmdb_id",
        "runtime": "runtime_minutes",
        "original_language": "original_language",
        "vote_average": "tmdb_rating",
        "vote_count": "tmdb_votes",
    }

    df.rename(
        columns=rename_map,
        inplace=True,
    )

    return df


# ============================================================
# Save Dataset
# ============================================================

def save_dataset(df: pd.DataFrame) -> None:

    DATA.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print("Dataset Saved")
    print("=" * 70)

    print(f"\nOutput : {OUTPUT_FILE}")
    print(f"Rows   : {len(df):,}")
    print(f"Columns: {len(df.columns)}")


# ============================================================
# Main Pipeline
# ============================================================

def main():

    df = load_dataset()

    df = clean_dataset(df)

    df = engineer_features(df)

    df = prepare_final_dataset(df)

    save_dataset(df)

    print("\n" + "=" * 70)
    print("CineMetrics Dataset Pipeline Completed")
    print("=" * 70)


if __name__ == "__main__":
    main()
