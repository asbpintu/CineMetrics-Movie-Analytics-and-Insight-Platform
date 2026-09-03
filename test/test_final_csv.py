import pandas as pd

file = "data/processed/cinemetrics_movies_2020_2026.csv"

df = pd.read_csv(file)

print("Rows:", len(df))
print("\nColumns:")
for i, col in enumerate(df.columns, start=1):
    print(f"{i:02d}. {col}")

print("\nData types:")
print(df.dtypes)

print("\nShape:", df.shape)