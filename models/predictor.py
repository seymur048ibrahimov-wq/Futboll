from models.poisson import probabilities
from models.form import recency_form, trend
from models.ensemble import combine, agreement
from analysis.uncertainty import assess

def predict(m):
    hf = recency_form(m.get("home_form",[]))
    af = recency_form(m.get("away_form",[]))
    ht = trend(m.get("home_form",[]))
    at = trend(m.get("away_form",[]))

    # Dynamic pre-match expected goals. No odds/market variables.
    home_lambda = max(0.20,
        0.52*m["home_xg"] + 0.24*m["away_xga"] +
        0.14*(0.8+hf) + 0.05*ht +
        0.05*(1 + m.get("home_attack_adj",0))
    )
    away_lambda = max(0.20,
        0.52*m["away_xg"] + 0.24*m["home_xga"] +
        0.14*(0.8+af) + 0.05*at +
        0.05*(1 + m.get("away_attack_adj",0))
    )

    # Lineup/injury adjustment supplied by the data layer.
    home_lambda *= max(0.75, min(1.20, 1+m.get("home_attack_adj",0)))
    away_lambda *= max(0.75, min(1.20, 1+m.get("away_attack_adj",0)))

    p = probabilities(home_lambda,away_lambda)

    elo_home = m["home_elo"] + m.get("home_dynamic_rating_adj",0)
    elo_away = m["away_elo"] + m.get("away_dynamic_rating_adj",0)
    diff = elo_home-elo_away+55
    ep = 1/(1+10**(-diff/400))
    elo = {"home":ep*(1-p["draw"]),"draw":p["draw"],
           "away":(1-ep)*(1-p["draw"])}

    xg_share = home_lambda/max(home_lambda+away_lambda,1e-9)
    xg = {"home":xg_share*(1-p["draw"]),"draw":p["draw"],
          "away":(1-xg_share)*(1-p["draw"])}

    final = combine(p,elo,xg)
    ag = agreement([{"home":p["home"],"draw":p["draw"],"away":p["away"]},
                    elo,xg])

    uncertainty = assess(m,final,ag)
    maxp = max(final.values())
    second = sorted(final.values())[-2]
    spread = maxp-second
    confidence = round(max(0,min(100,(50+130*spread)*uncertainty["quality"])))

    xg_gap = min(abs(home_lambda-away_lambda)/1.5,1)
    form_gap = min(abs(hf-af),1)
    score = round(45+25*xg_gap+15*form_gap+10*ag["agreement"]+
                  5*uncertainty["quality"]*10)
    score = max(0,min(100,score))

    if confidence >= 60 and score >= 60 and ag["agreement"] >= .55:
        signal="STRONG"
    elif confidence >= 50 and score >= 48 and ag["agreement"] >= .48:
        signal="GOOD"
    elif confidence >= 40 and score >= 38:
        signal="WATCH"
    else:
        signal="NO SIGNAL"

    return {
        "home_win":round(final["home"]*100,1),
        "draw":round(final["draw"]*100,1),
        "away_win":round(final["away"]*100,1),
        "alt_under":{k:{"under":round(v["under"]*100,1),
                        "over":round(v["over"]*100,1)}
                     for k,v in p["totals"].items()},
        "btts":round(p["btts"]*100,1),
        "no_btts":round(p["no_btts"]*100,1),
        "match_score":score,
        "confidence":confidence,
        "signal":signal,
        "model_agreement":round(ag["agreement"]*100,1),
        "agreement_winner":ag["winner"],
        "uncertainty_flags":uncertainty["issues"],
        "bookmaker_odds_used":False
    }
