def opponent_adjusted_form(results, opponent_ratings):
    if not results:
        return 0.5
    weighted = 0.0
    total = 0.0
    for result, opp in zip(results, opponent_ratings):
        # Stronger opponents increase the informational value of a good result.
        strength = max(0.70, min(1.30, opp / 1500.0))
        weighted += (result / 3.0) * strength
        total += strength
    return weighted / total if total else 0.5

def dynamic_rating(base, recent_form, trend=0.0, home_split=0.0):
    return base + 180*(recent_form-0.5) + 60*trend + 50*home_split
