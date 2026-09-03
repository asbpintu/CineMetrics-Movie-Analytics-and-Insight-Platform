from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

CSV_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "cinemetrics_movies_2020_2026.csv"
)

DATABASE_NAME = "CineMetrics"

SERVER = r"localhost\SQLEXPRESS"
DRIVER = "ODBC Driver 18 for SQL Server"


# ============================================================
# DATABASE CONNECTION
# ============================================================

connection_string = (
    f"mssql+pyodbc://@{SERVER}/{DATABASE_NAME}"
    f"?driver={DRIVER.replace(' ', '+')}"
    f"&trusted_connection=yes"
    f"&TrustServerCertificate=yes"
)

engine = create_engine(
    connection_string,
    fast_executemany=True
)


# ============================================================
# EXPECTED CSV COLUMNS
# ============================================================

EXPECTED_COLUMNS = [
    "backdrop_path",
    "budget",
    "genres",
    "movie_id",
    "original_language",
    "overview",
    "popularity",
    "poster_path",
    "production_companies",
    "production_countries",
    "release_date",
    "revenue",
    "runtime",
    "status",
    "title",
    "vote_average",
    "vote_count",
    "imdb_id",
    "tagline",
    "homepage",
    "directors",
    "writers",
    "cast_top_5",
]


# ============================================================
# LOAD CSV
# ============================================================

def load_csv():
    print("=" * 70)
    print("CineMetrics - CSV → Staging ETL")
    print("=" * 70)

    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"CSV file not found:\n{CSV_FILE}"
        )

    print(f"\nCSV file:")
    print(CSV_FILE)

    df = pd.read_csv(
        CSV_FILE,
        keep_default_na=True
    )

    print(f"\nRows loaded from CSV: {len(df):,}")

    print(f"Columns found: {len(df.columns)}")


    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    missing_columns = [
        col
        for col in EXPECTED_COLUMNS
        if col not in df.columns
    ]

    unexpected_columns = [
        col
        for col in df.columns
        if col not in EXPECTED_COLUMNS
    ]

    if missing_columns:
        raise ValueError(
            f"\nMissing expected columns:\n{missing_columns}"
        )

    if unexpected_columns:
        print(
            f"\nWarning - unexpected columns found:\n"
            f"{unexpected_columns}"
        )

    # Keep only expected columns and preserve order
    df = df[EXPECTED_COLUMNS]


    # --------------------------------------------------------
    # Data cleaning
    # --------------------------------------------------------

    string_columns = [
        "backdrop_path",
        "genres",
        "original_language",
        "overview",
        "poster_path",
        "production_companies",
        "production_countries",
        "status",
        "title",
        "imdb_id",
        "tagline",
        "homepage",
        "directors",
        "writers",
        "cast_top_5",
    ]

    for column in string_columns:
        df[column] = df[column].astype("string")


    # Convert release date
    df["release_date"] = pd.to_datetime(
        df["release_date"],
        errors="coerce"
    ).dt.date


    # Numeric columns
    numeric_columns = [
        "movie_id",
        "budget",
        "revenue",
        "runtime",
        "vote_count",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


    # Decimal columns
    decimal_columns = [
        "popularity",
        "vote_average",
    ]

    for column in decimal_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


    # --------------------------------------------------------
    # Remove duplicate movies
    # --------------------------------------------------------

    duplicate_count = df["movie_id"].duplicated().sum()

    print(
        f"\nDuplicate movie IDs found: "
        f"{duplicate_count:,}"
    )

    if duplicate_count > 0:
        df = df.drop_duplicates(
            subset=["movie_id"],
            keep="first"
        )

        print(
            f"Rows after duplicate removal: "
            f"{len(df):,}"
        )


    # --------------------------------------------------------
    # Validate movie IDs
    # --------------------------------------------------------

    null_movie_ids = df["movie_id"].isna().sum()

    print(
        f"Null movie IDs: {null_movie_ids:,}"
    )

    if null_movie_ids > 0:
        df = df.dropna(
            subset=["movie_id"]
        )


    # movie_id should be integer
    df["movie_id"] = df["movie_id"].astype("int64")


    return df


# ============================================================
# LOAD INTO SQL SERVER
# ============================================================

def load_to_sql(df):

    print("\nConnecting to SQL Server...")

    with engine.begin() as connection:

        print("Connection successful.")

        # ----------------------------------------------------
        # Clear staging table
        # ----------------------------------------------------

        print("\nClearing staging table...")

        connection.execute(
            text(
                "TRUNCATE TABLE stg.stg_movies"
            )
        )

        print("Staging table cleared.")

    # --------------------------------------------------------
    # Insert dataframe
    # --------------------------------------------------------

    print("\nLoading data into stg.stg_movies...")

    df.to_sql(
        name="stg_movies",
        con=engine,
        schema="stg",
        if_exists="append",
        index=False,
        chunksize=1000,
        method=None,
    )

    print("Staging load completed.")


# ============================================================
# VALIDATION
# ============================================================

def validate_load(expected_rows):

    print("\nValidating staging table...")

    with engine.connect() as connection:

        result = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stg.stg_movies
                """
            )
        )

        actual_rows = result.scalar()

    print(
        f"Expected rows : {expected_rows:,}"
    )

    print(
        f"SQL rows      : {actual_rows:,}"
    )

    if actual_rows != expected_rows:
        raise RuntimeError(
            "Row count mismatch between CSV and SQL staging table."
        )

    print("\nRow count validation: PASSED")


# ============================================================
# MAIN
# ============================================================

def main():

    df = load_csv()

    print("\nFinal dataframe shape:")
    print(df.shape)

    load_to_sql(df)

    validate_load(
        expected_rows=len(df)
    )

    print("\n" + "=" * 70)
    print("CSV → STAGING ETL COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()