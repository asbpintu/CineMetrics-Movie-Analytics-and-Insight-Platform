from pathlib import Path
import subprocess
import sys


# ============================================================
# Configuration
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA = ROOT / "data"
RAW = DATA / "raw"

DATASET = "pankajmaulekhi/tmdb-top-10000-movies-updated-till-2025"
FILE_NAME = "new_movies_full.csv"

OUTPUT_FILE = RAW / FILE_NAME


# ============================================================
# Download Dataset
# ============================================================

def download_dataset() -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        print(f"[SKIP] {FILE_NAME} already exists")
        return

    print("=" * 70)
    print("Downloading TMDB Top 10,000 Movies Dataset")
    print("=" * 70)

    command = [
        sys.executable,
        "-m",
        "kaggle",
        "datasets",
        "download",
        DATASET,
        "--file",
        FILE_NAME,
        "--path",
        str(RAW),
        "--unzip",
    ]

    print("\n[DOWNLOAD]")
    print(f"Dataset : {DATASET}")
    print(f"File    : {FILE_NAME}")
    print(f"Output  : {RAW}\n")

    result = subprocess.run(command)

    if result.returncode != 0:
        raise RuntimeError(
            "Kaggle dataset download failed."
        )

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            f"Downloaded file not found: {OUTPUT_FILE}"
        )

    print("\n[DONE]")
    print(f"Dataset saved to: {OUTPUT_FILE}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    download_dataset()