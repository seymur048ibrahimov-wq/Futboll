import math
from models.predictor import predict

def walk_forward(matches):
    # Input must be chronological. Features must represent information
    # available before each match. Future matches are never used.
    rows=[]
    for m in matches:
        if m.get("result") not in {"H","D","A"}:
            continue
        p=predict(m)
        probs=[p["home_win"]/100,p["draw"]/100,p["away_win"]/100]
        actual={"H":0,"D":1,"A":2}[m["result"]]
        pred=max(range(3),key=lambda i:probs[i])
        rows.append({
            "correct":pred==actual,
            "brier":sum((probs[i]-(1 if i==actual else 0))**2 for i in range(3)),
            "logloss":-math.log(max(probs[actual],1e-15))
        })
    if not rows: return {"matches":0}
    return {
        "matches":len(rows),
        "accuracy":round(sum(x["correct"] for x in rows)/len(rows)*100,2),
        "brier_1x2":round(sum(x["brier"] for x in rows)/len(rows),4),
        "log_loss":round(sum(x["logloss"] for x in rows)/len(rows),4)
    }
