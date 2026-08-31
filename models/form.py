def recency_form(results, decay=0.88):
    if not results:
        return 0.5
    weights = [decay**(len(results)-1-i) for i in range(len(results))]
    return sum(r*w for r,w in zip(results,weights))/(3*sum(weights))

def trend(results):
    if len(results) < 4:
        return 0.0
    cut = len(results)//2
    a = sum(results[:cut])/max(1,cut)
    b = sum(results[cut:])/max(1,len(results)-cut)
    return (b-a)/3
