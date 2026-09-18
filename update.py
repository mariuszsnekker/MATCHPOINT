
import os
import json
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent
KEY = os.environ.get("FOOTBALL_DATA_TOKEN", "")

now = datetime.datetime.now(datetime.timezone.utc)
start = (now - datetime.timedelta(days=30)).date()
end = (now + datetime.timedelta(days=7)).date()

matches = []
errors = []

# Zachowaj zakończone mecze z poprzedniej aktualizacji
history = []
data_file = ROOT / "data.json"

if data_file.exists():
    try:
        previous = json.loads(data_file.read_text(encoding="utf-8"))
        history = previous.get("history", [])

        for match in previous.get("matches", []):
            if match.get("status") == "FINISHED":
                history.append(match)
    except (OSError, ValueError, TypeError):
        history = []

# Usuń duplikaty na podstawie identyfikatora meczu
history = list({
    match["id"]: match
    for match in history
    if isinstance(match, dict) and match.get("id")
}.values())

# Dotychczasowe ligi
comps = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "PPL": "Primeira Liga",
    "CL": "Liga Mistrzów",
    "ELC": "Championship"
}

if KEY:
    for code, league in comps.items():
        try:
            params = urllib.parse.urlencode({
                "dateFrom": start.isoformat(),
                "dateTo": end.isoformat()
            })

            url = (
                "https://api.football-data.org/v4/"
                f"competitions/{code}/matches?{params}"
            )

            req = urllib.request.Request(
                url,
                headers={"X-Auth-Token": KEY}
            )

            with urllib.request.urlopen(req, timeout=22) as r:
                data = json.load(r)

            for m in data.get("matches", []):
                score = m.get("score", {}).get("fullTime") or {}

                matches.append({
                    "id": str(m["id"]),
                    "league": league,
                    "utc": m.get("utcDate"),
                    "home": m.get("homeTeam", {}).get("name") or "TBD",
                    "away": m.get("awayTeam", {}).get("name") or "TBD",
                    "status": m.get("status"),
                    "score": score
                })

        except Exception as e:
            errors.append(f"{league}: {e}")
else:
    errors.append("Brak FOOTBALL_DATA_TOKEN")

# Ligi norweskie - TheSportsDB
norway = {
    "4337": "Eliteserien",
    "4457": "OBOS-ligaen"
}

for league_id, league_name in norway.items():
    try:
        # Pobieranie sezonu 2026
        params = urllib.parse.urlencode({
            "id": league_id,
            "s": "2026"
        })

        url = (
            "https://www.thesportsdb.com/api/v1/json/3/"
            f"eventsseason.php?{params}"
        )

        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r)

        for m in data.get("events") or []:
            date = m.get("dateEvent")
            time = m.get("strTimestamp")

            if not date:
                continue

            match_date = datetime.date.fromisoformat(date)

            if not start <= match_date <= end:
                continue

            home_score = m.get("intHomeScore")
            away_score = m.get("intAwayScore")

            status = (
                "FINISHED"
                if m.get("strStatus") in ("FT", "Match Finished")
                else "SCHEDULED"
            )

            matches.append({
                "id": "tsdb-" + str(m.get("idEvent")),
                "league": league_name,
                "utc": time or date + "T12:00:00Z",
                "home": m.get("strHomeTeam") or "TBD",
                "away": m.get("strAwayTeam") or "TBD",
                "status": status,
                "score": {
                    "home": home_score,
                    "away": away_score
                }
            })

    except Exception as e:
        errors.append(f"{league_name}: {e}")

# Zapis danych
if not matches:
    raise SystemExit(
        "Nie pobrano meczów. " + "; ".join(errors)
    )

matches.sort(key=lambda m: m.get("utc") or "")
# Prognoza formy na podstawie 5 ostatnich meczów przed spotkaniem
predictions = []

finished = [
    m for m in matches + history
    if m.get("status") == "FINISHED"
    and m.get("utc")
    and m.get("score", {}).get("home") is not None
    and m.get("score", {}).get("away") is not None
]

for match in matches:
    if match.get("status") not in ("TIMED", "SCHEDULED"):
        continue

    kickoff = match.get("utc")
    if not kickoff:
        continue

    def team_form(team):
        previous = [
            m for m in finished
            if m["utc"] < kickoff
            and team in (m.get("home"), m.get("away"))
        ]
        previous.sort(key=lambda m: m["utc"], reverse=True)
        previous = previous[:5]

        points = 0
        for m in previous:
            home_goals = m["score"]["home"]
            away_goals = m["score"]["away"]
            goals_for, goals_against = (
                (home_goals, away_goals)
                if m["home"] == team
                else (away_goals, home_goals)
            )
            points += (
                3 if goals_for > goals_against
                else 1 if goals_for == goals_against
                else 0
            )

        return {"matches": len(previous), "points": points}

    home_form = team_form(match["home"])
    away_form = team_form(match["away"])

    predictions.append({
        "matchId": match["id"],
        "home": match["home"],
        "away": match["away"],
        "homeForm": home_form,
        "awayForm": away_form,
        "note": (
            "Za mało danych"
            if home_form["matches"] < 5 or away_form["matches"] < 5
            else "Porównanie formy z ostatnich 5 meczów"
        )
    })
result = {
    "updatedAt": now.isoformat(),
    "source": "football-data.org + TheSportsDB",
    "matches": matches,
    "errors": errors,
    "predictions": predictions,
    "history": history
}

(ROOT / "data.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(f"Zaktualizowano {len(matches)} meczów")
print(f"Błędy: {len(errors)}")
