# Synthetic Study: Temperature Variability and Species Richness

## Study claim

This study analyses the linear relationship between environmental temperature
variability (x) and species richness index (y) across 20 sampling sites.

Linear regression on the 20-site dataset produces:

- **Slope (coefficient): 2.4086**
- **Intercept: 1.1742**
- **R² = 0.9991**

The strong R² indicates that temperature variability is an excellent linear
predictor of species richness in this dataset.

## Reproduction

Run `study.py` from this directory. No external dependencies — pure Python stdlib.

```bash
python3 study.py
```

Expected output:
```
Slope (coefficient): 2.4086
Intercept:           1.1742
R²:                  0.9991
```

## Data

`data.csv` — 20 rows, columns `x` (temperature variability index) and
`y` (species richness index). All values are synthetic for demonstration purposes.
