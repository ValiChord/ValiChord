#!/usr/bin/env python3
"""
Synthetic Study: Linear relationship between environmental temperature
variability and species richness index across 20 sampling sites.

Claims: slope ≈ 2.31, R² ≈ 0.998
Run this script from the directory containing data.csv.
"""
import csv
import os

def main():
    data_path = os.path.join(os.path.dirname(__file__), 'data.csv')
    data = []
    with open(data_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append((float(row['x']), float(row['y'])))

    n = len(data)
    xs = [d[0] for d in data]
    ys = [d[1] for d in data]

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    num   = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denom = sum((x - x_mean) ** 2 for x in xs)

    slope     = num / denom
    intercept = y_mean - slope * x_mean

    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r2     = 1 - ss_res / ss_tot

    print(f"Slope (coefficient): {slope:.4f}")
    print(f"Intercept:           {intercept:.4f}")
    print(f"R²:                  {r2:.4f}")

if __name__ == '__main__':
    main()
