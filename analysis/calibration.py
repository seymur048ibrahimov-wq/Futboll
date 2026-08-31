def reliability_bins(predictions, bins=10):
    # predictions: [{"prob":0.72,"outcome":1}, ...]
    result=[]
    for i in range(bins):
        lo=i/bins; hi=(i+1)/bins
        bucket=[x for x in predictions
                if lo <= x["prob"] < hi or
                   (i==bins-1 and x["prob"]<=hi)]
        if not bucket: continue
        result.append({
            "range":f"{lo:.1f}-{hi:.1f}",
            "predicted":round(sum(x["prob"] for x in bucket)/len(bucket),3),
            "actual":round(sum(x["outcome"] for x in bucket)/len(bucket),3),
            "count":len(bucket)
        })
    return result
