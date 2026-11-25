"""Supported exact AMFI category label mappings, not inferred regulatory compliance."""
LABELS={"LARGE_CAP":"large cap fund","MID_CAP":"mid cap fund","SMALL_CAP":"small cap fund",
        "FLEXI_CAP":"flexi cap fund","INDEX":"index funds","LARGE_MID_CAP":"large & mid cap fund",
        "MULTI_CAP":"multi cap fund","AGGRESSIVE_HYBRID":"aggressive hybrid fund",
        "CORPORATE_BOND":"corporate bond fund","SHORT_DURATION":"short duration fund"}
CATEGORIES=tuple(LABELS)
DEBT=frozenset(("CORPORATE_BOND","SHORT_DURATION"))
SPECIALIZED=frozenset(("AGGRESSIVE_HYBRID",*DEBT))
COMPARABLE=frozenset(CATEGORIES)-SPECIALIZED-{"INDEX"}
