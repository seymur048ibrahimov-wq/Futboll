def assess(match, final_probs, agreement):
    issues = []
    required = ["home_form","away_form","home_xg","away_xg",
                "home_xga","away_xga","home_elo","away_elo"]
    missing = [x for x in required if match.get(x) is None]
    if missing:
        issues.append("missing_data")

    if agreement["agreement"] < 0.45:
        issues.append("model_disagreement")

    if max(final_probs.values()) < 0.35:
        issues.append("weak_1x2_edge")

    injuries = match.get("home_injuries",0)+match.get("away_injuries",0)
    if injuries >= 5:
        issues.append("lineup_uncertainty")

    if match.get("lineup_confirmed") is False:
        issues.append("lineup_not_confirmed")

    # xG provenance: real API xG is trusted fully. Shot-based estimates and
    # season-goals-average fallbacks are weaker signals, so they cost quality.
    xg_source = match.get("xg_source", "api")
    if xg_source == "estimated":
        issues.append("estimated_xg")
    elif xg_source == "fallback_goals_avg":
        issues.append("estimated_xg")
        issues.append("weak_xg_data")

    quality = max(0.0, 1.0-0.05*len(issues))
    return {"issues":issues,"quality":quality}
