"""
CineMetrics - Financial Data Enrichment
=======================================

Enriches missing/zero Budget and Revenue values using TMDB.

Rules:
    1. Existing non-zero Budget/Revenue values are NEVER overwritten.
    2. Only zero/null financial values are queried from TMDB.
    3. TMDB responses are cached locally.
    4. Script can safely be interrupted and resumed.
    5. Every update is recorded in an audit log.
    6. If TMDB has no financial value, the original value remains 0.
    7. No estimated/imputed financial values are created.

Input:
    data/processed/cinemetrics_movies_2020_2026.csv

Output:
    data/processed/cinemetrics_movies_2020_2026_enriched.csv
    data/processed/cinemetrics_financial_enrichment_log.csv

Cache:
    data/cache/tmdb_financials/

Environment:
    TMDB_READ_ACCESS_TOKEN=<your TMDB Bearer token>

Dependencies:
    pandas
    requests
    python-dotenv

Install:
    pip install pandas requests python-dotenv

Run:
    python scripts/enrich_financials.py

Optional:
    python scripts/enrich_financials.py --limit 100
    python scripts/enrich_financials.py --sleep 0.15
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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
    / "cinemetrics_movies_2020_2026_enriched.csv"
)

DEFAULT_LOG = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "cinemetrics_financial_enrichment_log.csv"
)

CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "cache"
    / "tmdb_financials"
)

ENV_FILE = PROJECT_ROOT / ".env"

TMDB_BASE_URL = "https://api.themoviedb.org/3"

REQUEST_TIMEOUT = 30

DEFAULT_SLEEP = 0.10

MAX_RETRIES = 5

# HTTP status codes worth retrying
RETRY_STATUS_CODES = {
    408,   # Request Timeout
    429,   # Too Many Requests
    500,
    502,
    503,
    504,
}


# ============================================================
# LOGGING
# ============================================================

def log(message: str = "") -> None:
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich missing CineMetrics budget/revenue values using TMDB."
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Input CSV path.",
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output enriched CSV path.",
    )

    parser.add_argument(
        "--log",
        dest="log_file",
        default=str(DEFAULT_LOG),
        help="Financial enrichment audit log path.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP,
        help=f"Delay between TMDB requests in seconds. Default: {DEFAULT_SLEEP}",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only N movies. Useful for testing.",
    )

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore existing cache and request TMDB again.",
    )

    return parser.parse_args()


# ============================================================
# ENVIRONMENT
# ============================================================

def load_tmdb_token() -> str:
    """
    Load TMDB Bearer token from .env.

    Expected:
        TMDB_READ_ACCESS_TOKEN=xxxxxxxx
    """

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    token = os.getenv("TMDB_READ_ACCESS_TOKEN")

    if not token:
        raise RuntimeError(
            "\nTMDB_READ_ACCESS_TOKEN was not found.\n\n"
            "Add your existing TMDB Bearer token to .env:\n\n"
            "TMDB_READ_ACCESS_TOKEN=YOUR_TOKEN_HERE\n"
        )

    return token.strip()


# ============================================================
# HTTP SESSION
# ============================================================

def create_session(token: str) -> requests.Session:
    """Create reusable TMDB HTTP session."""

    session = requests.Session()

    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CineMetrics-Financial-Enrichment/1.0",
        }
    )

    return session


# ============================================================
# CACHE
# ============================================================

def cache_path(movie_id: int) -> Path:
    """Return cache file for a TMDB movie."""

    return CACHE_DIR / f"{movie_id}.json"


def load_cached_movie(
    movie_id: int,
) -> Optional[Dict[str, Any]]:
    """Load cached TMDB response."""

    path = cache_path(movie_id)

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    except (json.JSONDecodeError, OSError):
        return None


def save_cached_movie(
    movie_id: int,
    data: Dict[str, Any],
) -> None:
    """Save TMDB response to cache."""

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = cache_path(movie_id)

    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp_path.replace(path)


# ============================================================
# TMDB API
# ============================================================

def fetch_tmdb_movie(
    session: requests.Session,
    movie_id: int,
    force_refresh: bool = False,
) -> tuple[Optional[Dict[str, Any]], str]:
    """
    Fetch movie details from TMDB.

    Returns:
        (data, status)

    status examples:
        cached
        fetched
        not_found
        error
        failed
    """

    if not force_refresh:
        cached = load_cached_movie(movie_id)

        if cached is not None:
            return cached, "cached"

    url = f"{TMDB_BASE_URL}/movie/{movie_id}"

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.RequestException as exc:

            if attempt >= MAX_RETRIES:
                log(
                    f"TMDB request failed for {movie_id}: "
                    f"{type(exc).__name__}"
                )

                return None, "error"

            wait_time = min(
                30,
                (2 ** (attempt - 1)) + random.random(),
            )

            log(
                f"Request error for {movie_id}. "
                f"Retrying in {wait_time:.1f}s..."
            )

            time.sleep(wait_time)

            continue

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if response.status_code == 200:

            try:
                data = response.json()
            except ValueError:
                log(f"Invalid JSON returned by TMDB for {movie_id}.")
                return None, "error"

            save_cached_movie(
                movie_id,
                data,
            )

            return data, "fetched"

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        if response.status_code == 404:

            data = {
                "_cinemetrics_status": "not_found",
                "_tmdb_movie_id": movie_id,
            }

            save_cached_movie(
                movie_id,
                data,
            )

            return None, "not_found"

        # ----------------------------------------------------
        # RETRYABLE ERROR
        # ----------------------------------------------------

        if response.status_code in RETRY_STATUS_CODES:

            retry_after = response.headers.get("Retry-After")

            if retry_after:
                try:
                    wait_time = float(retry_after)
                except ValueError:
                    wait_time = 2 ** (attempt - 1)
            else:
                wait_time = 2 ** (attempt - 1)

            wait_time += random.uniform(0, 0.5)

            if attempt < MAX_RETRIES:

                log(
                    f"TMDB HTTP {response.status_code} "
                    f"for movie {movie_id}. "
                    f"Retry {attempt}/{MAX_RETRIES} "
                    f"in {wait_time:.1f}s..."
                )

                time.sleep(wait_time)

                continue

        # ----------------------------------------------------
        # OTHER ERROR
        # ----------------------------------------------------

        log(
            f"TMDB HTTP {response.status_code} "
            f"for movie {movie_id}."
        )

        return None, "error"

    return None, "failed"


# ============================================================
# DATA HELPERS
# ============================================================

def is_missing_financial_value(value: Any) -> bool:
    """
    Determine whether a budget/revenue value is missing.

    Treat:
        NaN
        None
        ""
        0
        0.0

    as missing.

    Negative values are NOT treated as missing.
    """

    if value is None:
        return True

    try:

        if pd.isna(value):
            return True

    except (TypeError, ValueError):
        pass

    if isinstance(value, str):

        value = value.strip()

        if value == "":
            return True

        try:
            value = float(value)
        except ValueError:
            return False

    try:
        return float(value) == 0
    except (TypeError, ValueError):
        return False


def normalize_money(value: Any) -> int:
    """
    Convert TMDB financial value to integer.

    TMDB normally returns integer USD values.
    """

    if value is None:
        return 0

    try:
        value = float(value)

        if pd.isna(value):
            return 0

        if value <= 0:
            return 0

        return int(round(value))

    except (TypeError, ValueError):
        return 0


def normalize_movie_id(value: Any) -> Optional[int]:
    """Convert movie ID into an integer safely."""

    if value is None:
        return None

    try:

        if pd.isna(value):
            return None

    except (TypeError, ValueError):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# ============================================================
# FINANCIAL STATUS
# ============================================================

def determine_financial_status(
    budget: Any,
    revenue: Any,
) -> str:
    """Return financial data completeness status."""

    budget_missing = is_missing_financial_value(budget)
    revenue_missing = is_missing_financial_value(revenue)

    if not budget_missing and not revenue_missing:
        return "Complete"

    if budget_missing and revenue_missing:
        return "Both Missing"

    if budget_missing:
        return "Budget Missing"

    return "Revenue Missing"


# ============================================================
# SOURCE LABEL
# ============================================================

def determine_source(
    original_value: Any,
    current_source: Optional[str],
) -> str:
    """
    Determine source label.

    Existing values:
        Original

    Newly enriched:
        TMDB

    Still unavailable:
        Unavailable
    """

    if not is_missing_financial_value(original_value):
        return "Original"

    if current_source == "TMDB":
        return "TMDB"

    return "Unavailable"


# ============================================================
# DATA QUALITY SUMMARY
# ============================================================

def print_financial_summary(
    df: pd.DataFrame,
    title: str,
) -> None:

    total = len(df)

    budget_missing = df["budget"].apply(
        is_missing_financial_value
    ).sum()

    revenue_missing = df["revenue"].apply(
        is_missing_financial_value
    ).sum()

    both_missing = (
        df["budget"].apply(is_missing_financial_value)
        & df["revenue"].apply(is_missing_financial_value)
    ).sum()

    budget_complete = total - budget_missing
    revenue_complete = total - revenue_missing

    print()
    print("=" * 72)
    print(title)
    print("=" * 72)

    print(f"Total movies             : {total:,}")

    print(
        f"Budget available         : "
        f"{budget_complete:,} "
        f"({budget_complete / total * 100:.1f}%)"
    )

    print(
        f"Budget missing/zero      : "
        f"{budget_missing:,} "
        f"({budget_missing / total * 100:.1f}%)"
    )

    print(
        f"Revenue available        : "
        f"{revenue_complete:,} "
        f"({revenue_complete / total * 100:.1f}%)"
    )

    print(
        f"Revenue missing/zero     : "
        f"{revenue_missing:,} "
        f"({revenue_missing / total * 100:.1f}%)"
    )

    print(
        f"Both missing/zero        : "
        f"{both_missing:,} "
        f"({both_missing / total * 100:.1f}%)"
    )

    print("=" * 72)


# ============================================================
# MAIN ENRICHMENT
# ============================================================

def enrich_financials(
    df: pd.DataFrame,
    session: requests.Session,
    sleep_seconds: float,
    force_refresh: bool = False,
    limit: Optional[int] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    # --------------------------------------------------------
    # Ensure required columns exist
    # --------------------------------------------------------

    required_columns = {
        "movie_id",
        "budget",
        "revenue",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:

        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    # --------------------------------------------------------
    # Add source columns if they don't exist
    # --------------------------------------------------------

    if "budget_source" not in df.columns:
        df["budget_source"] = ""

    if "revenue_source" not in df.columns:
        df["revenue_source"] = ""

    if "financial_data_status" not in df.columns:
        df["financial_data_status"] = ""

    # --------------------------------------------------------
    # Initialize source columns
    # --------------------------------------------------------

    for index in df.index:

        budget = df.at[index, "budget"]
        revenue = df.at[index, "revenue"]

        current_budget_source = (
            str(df.at[index, "budget_source"]).strip()
            if pd.notna(df.at[index, "budget_source"])
            else ""
        )

        current_revenue_source = (
            str(df.at[index, "revenue_source"]).strip()
            if pd.notna(df.at[index, "revenue_source"])
            else ""
        )

        # Preserve source if already marked as TMDB.
        if not current_budget_source:
            df.at[index, "budget_source"] = (
                "Original"
                if not is_missing_financial_value(budget)
                else "Unavailable"
            )

        if not current_revenue_source:
            df.at[index, "revenue_source"] = (
                "Original"
                if not is_missing_financial_value(revenue)
                else "Unavailable"
            )

        df.at[index, "financial_data_status"] = (
            determine_financial_status(
                budget,
                revenue,
            )
        )

    # --------------------------------------------------------
    # Determine rows requiring TMDB
    # --------------------------------------------------------

    needs_budget = df["budget"].apply(
        is_missing_financial_value
    )

    needs_revenue = df["revenue"].apply(
        is_missing_financial_value
    )

    needs_enrichment = needs_budget | needs_revenue

    candidate_indices = list(
        df.index[needs_enrichment]
    )

    if limit is not None:
        candidate_indices = candidate_indices[:limit]

    total_candidates = len(candidate_indices)

    log()
    log(
        f"Movies requiring financial enrichment: "
        f"{total_candidates:,}"
    )

    # --------------------------------------------------------
    # Audit records
    # --------------------------------------------------------

    audit_records = []

    enriched_budget_count = 0
    enriched_revenue_count = 0

    unchanged_budget_count = 0
    unchanged_revenue_count = 0

    unavailable_budget_count = 0
    unavailable_revenue_count = 0

    request_count = 0
    cache_count = 0

    # --------------------------------------------------------
    # Process movies
    # --------------------------------------------------------

    for position, index in enumerate(
        candidate_indices,
        start=1,
    ):

        movie_id = normalize_movie_id(
            df.at[index, "movie_id"]
        )

        title = str(
            df.at[index, "title"]
        ) if "title" in df.columns else ""

        imdb_id = str(
            df.at[index, "imdb_id"]
        ) if "imdb_id" in df.columns else ""

        original_budget = df.at[
            index,
            "budget",
        ]

        original_revenue = df.at[
            index,
            "revenue",
        ]

        original_budget_missing = (
            is_missing_financial_value(
                original_budget
            )
        )

        original_revenue_missing = (
            is_missing_financial_value(
                original_revenue
            )
        )

        # ----------------------------------------------------
        # Invalid TMDB ID
        # ----------------------------------------------------

        if movie_id is None:

            log(
                f"[{position}/{total_candidates}] "
                f"Invalid movie_id | {title}"
            )

            audit_records.append(
                {
                    "processed_at_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),

                    "movie_id": "",
                    "imdb_id": imdb_id,
                    "title": title,

                    "original_budget": original_budget,
                    "original_revenue": original_revenue,

                    "tmdb_budget": None,
                    "tmdb_revenue": None,

                    "final_budget": df.at[index, "budget"],
                    "final_revenue": df.at[index, "revenue"],

                    "budget_updated": False,
                    "revenue_updated": False,

                    "budget_source": df.at[
                        index,
                        "budget_source",
                    ],

                    "revenue_source": df.at[
                        index,
                        "revenue_source",
                    ],

                    "financial_data_status": df.at[
                        index,
                        "financial_data_status",
                    ],

                    "api_status": "invalid_movie_id",
                    "source": "Unavailable",
                }
            )

            continue

        # ----------------------------------------------------
        # TMDB request
        # ----------------------------------------------------

        tmdb_data, api_status = fetch_tmdb_movie(
            session=session,
            movie_id=movie_id,
            force_refresh=force_refresh,
        )

        if api_status == "cached":
            cache_count += 1
        elif api_status == "fetched":
            request_count += 1

        tmdb_budget = None
        tmdb_revenue = None

        if tmdb_data:

            tmdb_budget = normalize_money(
                tmdb_data.get("budget")
            )

            tmdb_revenue = normalize_money(
                tmdb_data.get("revenue")
            )

        # ----------------------------------------------------
        # Existing values are NEVER overwritten
        # ----------------------------------------------------

        final_budget = df.at[
            index,
            "budget",
        ]

        final_revenue = df.at[
            index,
            "revenue",
        ]

        budget_updated = False
        revenue_updated = False

        # ----------------------------------------------------
        # BUDGET
        # ----------------------------------------------------

        if original_budget_missing:

            if tmdb_budget > 0:

                df.at[
                    index,
                    "budget",
                ] = tmdb_budget

                df.at[
                    index,
                    "budget_source",
                ] = "TMDB"

                budget_updated = True

                enriched_budget_count += 1

            else:

                df.at[
                    index,
                    "budget_source",
                ] = "Unavailable"

                unavailable_budget_count += 1

        else:

            # Existing non-zero value stays untouched.
            unchanged_budget_count += 1

            df.at[
                index,
                "budget_source",
            ] = "Original"

        # ----------------------------------------------------
        # REVENUE
        # ----------------------------------------------------

        if original_revenue_missing:

            if tmdb_revenue > 0:

                df.at[
                    index,
                    "revenue",
                ] = tmdb_revenue

                df.at[
                    index,
                    "revenue_source",
                ] = "TMDB"

                revenue_updated = True

                enriched_revenue_count += 1

            else:

                df.at[
                    index,
                    "revenue_source",
                ] = "Unavailable"

                unavailable_revenue_count += 1

        else:

            # Existing non-zero value stays untouched.
            unchanged_revenue_count += 1

            df.at[
                index,
                "revenue_source",
            ] = "Original"

        # ----------------------------------------------------
        # Final values
        # ----------------------------------------------------

        final_budget = df.at[
            index,
            "budget",
        ]

        final_revenue = df.at[
            index,
            "revenue",
        ]

        final_status = determine_financial_status(
            final_budget,
            final_revenue,
        )

        df.at[
            index,
            "financial_data_status",
        ] = final_status

        # ----------------------------------------------------
        # Audit log
        # ----------------------------------------------------

        audit_records.append(
            {
                "processed_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),

                "movie_id": movie_id,
                "imdb_id": imdb_id,
                "title": title,

                "original_budget": original_budget,
                "original_revenue": original_revenue,

                "tmdb_budget": tmdb_budget,
                "tmdb_revenue": tmdb_revenue,

                "final_budget": final_budget,
                "final_revenue": final_revenue,

                "budget_updated": budget_updated,
                "revenue_updated": revenue_updated,

                "budget_source": df.at[
                    index,
                    "budget_source",
                ],

                "revenue_source": df.at[
                    index,
                    "revenue_source",
                ],

                "financial_data_status": final_status,

                "api_status": api_status,

                "source": (
                    "TMDB"
                    if budget_updated or revenue_updated
                    else (
                        "Original"
                        if (
                            not original_budget_missing
                            or not original_revenue_missing
                        )
                        else "Unavailable"
                    )
                ),
            }
        )

        # ----------------------------------------------------
        # Progress output
        # ----------------------------------------------------

        if (
            position == 1
            or position % 25 == 0
            or position == total_candidates
        ):

            log(
                f"[{position}/{total_candidates}] "
                f"{title[:55]} | "
                f"Budget={'TMDB' if budget_updated else '—'} | "
                f"Revenue={'TMDB' if revenue_updated else '—'}"
            )

        # ----------------------------------------------------
        # Rate limiting
        # ----------------------------------------------------

        if position < total_candidates:
            time.sleep(
                max(0, sleep_seconds)
            )

    # ========================================================
    # Return
    # ========================================================

    audit_df = pd.DataFrame(
        audit_records
    )

    # Keep numeric financial columns clean.
    df["budget"] = pd.to_numeric(
        df["budget"],
        errors="coerce",
    ).fillna(0).astype("int64")

    df["revenue"] = pd.to_numeric(
        df["revenue"],
        errors="coerce",
    ).fillna(0).astype("int64")

    return df, audit_df


# ============================================================
# VALIDATION
# ============================================================

def validate_enriched_data(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
) -> None:

    print()
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)

    # --------------------------------------------------------
    # Row count
    # --------------------------------------------------------

    print(
        f"Rows before enrichment : {len(before_df):,}"
    )

    print(
        f"Rows after enrichment  : {len(after_df):,}"
    )

    if len(before_df) != len(after_df):
        raise RuntimeError(
            "Row count changed during enrichment."
        )

    # --------------------------------------------------------
    # Movie ID uniqueness
    # --------------------------------------------------------

    duplicate_ids = after_df[
        after_df["movie_id"].duplicated(
            keep=False
        )
    ]

    print(
        f"Duplicate movie IDs     : "
        f"{len(duplicate_ids):,}"
    )

    if len(duplicate_ids) > 0:
        raise RuntimeError(
            "Duplicate movie IDs detected after enrichment."
        )

    # --------------------------------------------------------
    # Existing values must not change
    # --------------------------------------------------------

    for column in [
        "budget",
        "revenue",
    ]:

        before_values = pd.to_numeric(
            before_df[column],
            errors="coerce",
        ).fillna(0)

        after_values = pd.to_numeric(
            after_df[column],
            errors="coerce",
        ).fillna(0)

        existing_mask = before_values > 0

        changed_existing = (
            before_values[existing_mask]
            != after_values[existing_mask]
        ).sum()

        print(
            f"Existing {column} values changed : "
            f"{changed_existing:,}"
        )

        if changed_existing > 0:
            raise RuntimeError(
                f"Existing non-zero {column} values "
                "were modified."
            )

    print()
    print("Validation passed.")
    print("=" * 72)


# ============================================================
# SAVE
# ============================================================

def save_results(
    df: pd.DataFrame,
    audit_df: pd.DataFrame,
    output_path: Path,
    log_path: Path,
) -> None:

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Save enriched dataset
    # --------------------------------------------------------

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # Save audit log
    # --------------------------------------------------------

    audit_df.to_csv(
        log_path,
        index=False,
        encoding="utf-8-sig",
    )

    log(
        f"Enriched CSV saved: {output_path}"
    )

    log(
        f"Audit log saved    : {log_path}"
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

def print_final_summary(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    audit_df: pd.DataFrame,
) -> None:

    before_budget_missing = before_df[
        "budget"
    ].apply(
        is_missing_financial_value
    ).sum()

    before_revenue_missing = before_df[
        "revenue"
    ].apply(
        is_missing_financial_value
    ).sum()

    after_budget_missing = after_df[
        "budget"
    ].apply(
        is_missing_financial_value
    ).sum()

    after_revenue_missing = after_df[
        "revenue"
    ].apply(
        is_missing_financial_value
    ).sum()

    budget_filled = (
        before_budget_missing
        - after_budget_missing
    )

    revenue_filled = (
        before_revenue_missing
        - after_revenue_missing
    )

    print()
    print("=" * 72)
    print("CINEMETRICS FINANCIAL ENRICHMENT COMPLETE")
    print("=" * 72)

    print(
        f"Movies processed             : "
        f"{len(after_df):,}"
    )

    print()

    print(
        f"Budget missing before        : "
        f"{before_budget_missing:,}"
    )

    print(
        f"Budget values filled         : "
        f"{budget_filled:,}"
    )

    print(
        f"Budget still unavailable     : "
        f"{after_budget_missing:,}"
    )

    print()

    print(
        f"Revenue missing before       : "
        f"{before_revenue_missing:,}"
    )

    print(
        f"Revenue values filled        : "
        f"{revenue_filled:,}"
    )

    print(
        f"Revenue still unavailable    : "
        f"{after_revenue_missing:,}"
    )

    print()

    if not audit_df.empty:

        budget_tmdb = (
            audit_df["budget_source"]
            .eq("TMDB")
            .sum()
        )

        revenue_tmdb = (
            audit_df["revenue_source"]
            .eq("TMDB")
            .sum()
        )

        print(
            f"Budget enriched from TMDB    : "
            f"{budget_tmdb:,}"
        )

        print(
            f"Revenue enriched from TMDB   : "
            f"{revenue_tmdb:,}"
        )

        print()

        print(
            "Financial status distribution:"
        )

        status_counts = (
            after_df[
                "financial_data_status"
            ]
            .value_counts()
        )

        for status, count in status_counts.items():

            print(
                f"  {status:<20} : {count:,}"
            )

    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    log_path = Path(args.log_file)

    print()
    print("=" * 72)
    print("CineMetrics - Financial Data Enrichment")
    print("=" * 72)

    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not input_path.exists():

        raise FileNotFoundError(
            f"\nInput CSV not found:\n{input_path}\n"
        )

    # --------------------------------------------------------
    # Token
    # --------------------------------------------------------

    token = load_tmdb_token()

    log("TMDB token loaded successfully.")

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log(
        f"TMDB cache directory: {CACHE_DIR}"
    )

    # --------------------------------------------------------
    # Load CSV
    # --------------------------------------------------------

    log(
        f"Loading CSV: {input_path}"
    )

    df = pd.read_csv(
        input_path,
        low_memory=False,
    )

    log(
        f"Loaded {len(df):,} rows."
    )

    # --------------------------------------------------------
    # Initial validation
    # --------------------------------------------------------

    print_financial_summary(
        df,
        "BEFORE ENRICHMENT",
    )

    # --------------------------------------------------------
    # Keep original copy for validation
    # --------------------------------------------------------

    before_df = df.copy(
        deep=True
    )

    # --------------------------------------------------------
    # Create HTTP session
    # --------------------------------------------------------

    session = create_session(
        token
    )

    # --------------------------------------------------------
    # Enrichment
    # --------------------------------------------------------

    start_time = time.time()

    enriched_df, audit_df = enrich_financials(
        df=df,
        session=session,
        sleep_seconds=args.sleep,
        force_refresh=args.force_refresh,
        limit=args.limit,
    )

    elapsed = time.time() - start_time

    log(
        f"Enrichment execution time: "
        f"{elapsed / 60:.2f} minutes"
    )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    validate_enriched_data(
        before_df=before_df,
        after_df=enriched_df,
    )

    # --------------------------------------------------------
    # Final financial summary
    # --------------------------------------------------------

    print_financial_summary(
        enriched_df,
        "AFTER ENRICHMENT",
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_results(
        df=enriched_df,
        audit_df=audit_df,
        output_path=output_path,
        log_path=log_path,
    )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print_final_summary(
        before_df=before_df,
        after_df=enriched_df,
        audit_df=audit_df,
    )

    print()
    print("Next step:")
    print(
        "Validate the enriched CSV before loading it into SQL Server."
    )
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("Process interrupted by user.")
        print("Cached TMDB responses are preserved.")
        print("Run the script again to continue.")

        sys.exit(1)

    except Exception as exc:

        print()
        print("=" * 72)
        print("ERROR")
        print("=" * 72)
        print(str(exc))
        print("=" * 72)

        sys.exit(1)