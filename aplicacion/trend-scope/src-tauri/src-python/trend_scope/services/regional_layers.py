"""Shared result metadata for temporal layers."""


def temporal_layer(kind, area, start, end, field, **data):
    span = (end - start).days + 1
    cadence = "daily" if span <= 93 else "monthly" if span <= 3652 else "yearly"
    return {"kind": kind, "area": area, "start": str(start), "end": str(end),
            "cadence": cadence, "field": field, **data}
