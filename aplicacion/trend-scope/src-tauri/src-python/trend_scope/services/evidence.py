"""Reproducible descriptive evidence over the complete returned series."""

import math
from datetime import date
from statistics import fmean


def summarize_series(series):
    rows = []
    for point in series.get("points", []):
        value = point.get("value")
        stamp = str(point.get("month", ""))
        try:
            day = date.fromisoformat(stamp + "-01" if len(stamp) == 7 else stamp[:10])
        except ValueError:
            continue
        if type(value) in (int, float) and math.isfinite(value):
            rows.append((day, float(value)))
    rows.sort(key=lambda row: row[0])
    result = {key: series.get(key) for key in
              ("id", "provider", "product", "variable", "unit", "coordinates", "location", "url", "retrievedAt")}
    result.update({"method": "descriptive-v1", "cadence": series.get("cadence", "monthly"),
                   "returnedCount": len(series.get("points", [])), "validCount": len(rows),
                   "missingOrInvalidCount": len(series.get("points", [])) - len(rows),
                   "limitations": ["Statistics describe available observations only; absent timestamps may not be counted.",
                                    "Mean is an unweighted mean of native observations, not an annual total or area average.",
                                    "OLS trend is descriptive: no seasonal adjustment, autocorrelation correction, confidence interval or causal attribution."]})
    if not rows:
        return result
    values = [row[1] for row in rows]
    result.update({"start": rows[0][0].isoformat(), "end": rows[-1][0].isoformat(),
                   "mean": fmean(values), "minimum": min(values), "maximum": max(values)})
    if len(rows) >= 3 and rows[-1][0] > rows[0][0]:
        x = [(row[0] - rows[0][0]).days / 365.2425 for row in rows]
        mx, my = fmean(x), fmean(values)
        denominator = sum((value - mx) ** 2 for value in x)
        slope = sum((t - mx) * (v - my) for t, v in zip(x, values)) / denominator
        residuals = sum((v - (my + slope * (t - mx))) ** 2 for t, v in zip(x, values))
        variance = sum((v - my) ** 2 for v in values)
        result["trend"] = {"method": "ordinary-least-squares", "perYear": slope,
                           "unit": f"{series.get('unit', '')}/year", "rSquared": 1 - residuals / variance if variance else None,
                           "spanYears": x[-1], "confidenceInterval": None}
    return result


def with_evidence(series):
    return [{**item, "summary": summarize_series(item)} for item in series]
