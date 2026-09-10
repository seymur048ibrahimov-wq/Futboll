import json
from pathlib import Path
from analysis.ranking import rank_matches,format_match
from database.db import init_db,save

def main():
    init_db()
    matches=json.loads(Path("data/demo_matches.json").read_text(encoding="utf-8"))
    ranked=rank_matches(matches)
    print("\n=== FOOTBALL AI V3 — INDEPENDENT ===\n")
    for i,(m,p) in enumerate(ranked,1):
        print(format_match(m,p,i))
        print("-"*65)
        save(m,p)

if __name__=="__main__":
    main()
