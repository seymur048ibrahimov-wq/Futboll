from models.predictor import predict

def rank_matches(matches):
    scored=[(m,predict(m)) for m in matches]
    # Strong signals first; no-signal games are pushed down.
    return sorted(scored,key=lambda x:(
        x[1]["signal"]=="NO SIGNAL",
        -x[1]["confidence"],
        -x[1]["match_score"],
        -x[1]["model_agreement"]
    ))

def format_match(m,p,rank=None):
    pre=f"{rank}. " if rank else ""
    lines=[
        f"{pre}🔥 {m['home']} — {m['away']}",
        f"🏆 {m['league']}",
        "",
        "🎯 1X2 — ƏSAS",
        f"1: {p['home_win']}% | X: {p['draw']}% | 2: {p['away_win']}%",
        "",
        "⚽ ALT / ÜST"
    ]
    for l in ["0.5","1.5","2.5","3.5","4.5","5.5","6.5"]:
        x=p["alt_under"][l]
        lines.append(f"{l}: Alt {x['under']}% | Üst {x['over']}%")
    lines += [
        "",
        f"🎯 BTTS: {p['btts']}%",
        f"📊 Match Score: {p['match_score']}/100",
        f"🧠 Confidence: {p['confidence']}/100",
        f"🤝 Model Agreement: {p['model_agreement']}%",
        f"🚦 Signal: {p['signal']}",
        f"⚠️ Flags: {', '.join(p['uncertainty_flags']) or 'none'}",
    ]
    xg_source = m.get("xg_source")
    if xg_source == "estimated":
        lines.append("📐 xG mənbəyi: ŞUT-ƏSASLI ESTİMASİYA")
    elif xg_source == "fallback_goals_avg":
        lines.append("📐 xG mənbəyi: QOL ORTALAMASI (zəif)")
    elif xg_source == "api":
        lines.append("📐 xG mənbəyi: API (real)")
    lines.append("🚫 Bukmeyker: MODELƏ DAXİL DEYİL")
    return "\n".join(lines)
