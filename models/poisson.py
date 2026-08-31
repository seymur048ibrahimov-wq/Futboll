import math

def pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)

def matrix(h_lam, a_lam, max_goals=10):
    return [[pmf(h,h_lam)*pmf(a,a_lam)
             for a in range(max_goals+1)]
            for h in range(max_goals+1)]

def probabilities(h_lam, a_lam):
    m = matrix(h_lam,a_lam)
    home = sum(m[h][a] for h in range(11) for a in range(11) if h>a)
    draw = sum(m[h][a] for h in range(11) for a in range(11) if h==a)
    away = sum(m[h][a] for h in range(11) for a in range(11) if h<a)
    totals = {}
    for line in [0.5,1.5,2.5,3.5,4.5,5.5,6.5]:
        n = int(line-0.5)
        under = sum(m[h][a] for h in range(11) for a in range(11)
                    if h+a <= n)
        totals[str(line)] = {"under":under,"over":1-under}
    btts = sum(m[h][a] for h in range(1,11) for a in range(1,11))
    return {"home":home,"draw":draw,"away":away,
            "totals":totals,"btts":btts,"no_btts":1-btts}
