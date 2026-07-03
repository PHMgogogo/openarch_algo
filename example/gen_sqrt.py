import csv
import math
import os

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "y_2x.csv")
ROWS = 100

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["x", "y"])
    for x in range(1, ROWS + 1):
        writer.writerow([x, 2 * x])

print(f"Wrote {ROWS} rows to {OUT_PATH}")
