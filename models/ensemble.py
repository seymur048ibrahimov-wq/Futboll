def normalize(p):
    s = sum(p.values())
    return {k:v/s for k,v in p.items()} if s else p

def combine(poisson, elo, xg, weights=(0.45,0.25,0.30)):
    return normalize({
        k: weights[0]*poisson[k] + weights[1]*elo[k] + weights[2]*xg[k]
        for k in ("home","draw","away")
    })

def agreement(p_list):
    winners = [max(p,key=p.get) for p in p_list]
    counts = {x:winners.count(x) for x in set(winners)}
    winner = max(counts,key=counts.get)
    return {
        "winner": winner,
        "votes": counts.get(winner,0),
        "total": len(winners),
        "agreement": counts.get(winner,0)/len(winners) if winners else 0
    }
