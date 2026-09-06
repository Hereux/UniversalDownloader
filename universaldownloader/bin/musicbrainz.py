import re, difflib
import threading
import time

import requests
from requests.adapters import HTTPAdapter, Retry
from dataclasses import dataclass

# MusicBrainz erlaubt nur 1 Request/Sekunde pro IP; bei paralleler Verifikation mehrerer
# Tracks muss der MB-Fallback deshalb serialisiert werden (Deezer bleibt parallel).
_mb_lock = threading.Lock()

session = requests.Session()
session.headers.update({"User-Agent": "UniversalDownloader/0.5 ( maklihereux@gmail.com )"})
session.mount("https://", HTTPAdapter(max_retries=Retry(
    total=2, connect=1, backoff_factor=0.5,
    status_forcelist=[429, 502, 503, 504], allowed_methods=["GET"])))

REMIX_RE = re.compile(r"\b(remix|edit|mix|bootleg|rework|vip)\b", re.I)

@dataclass
class Match:
    status: str
    artist: str | None
    title: str | None
    score: int
    similarity: float

def _credit(rec):
    out = ""
    for p in rec.get("artist-credit", []):
        out += p.get("name", "") + p.get("joinphrase", "")
    return out.strip()


LUCENE_RE = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


def _escape(s):
    s = LUCENE_RE.sub(r"\\\1", s)
    return re.sub(r"\b(AND|OR|NOT)\b", lambda m: m.group().lower(), s)


def _query(artist, title, retry=False):
    if retry:
        q = f'artist:({_escape(artist)}) AND recording:({_escape(title)})'
    else:
        q = f'artist:"{artist}" AND recording:"{title}"'

    r = session.get("https://musicbrainz.org/ws/2/recording",
                    params={"query": q, "fmt": "json", "limit": 3},
                    timeout=(5, 20))

    time.sleep(1.1)
    data = r.json()
    if "error" in data:
        raise requests.RequestException(data["error"])
    return data.get("recordings", [])


def _search_musicbrainz(artist, title):
    """Bester Treffer plus Ähnlichkeit zur Eingabe."""
    try:
        recs = _query(artist, title)

        if not recs:
            recs = _query(artist, title, retry=True)
    except requests.RequestException as e:
        print(f"MB fehlgeschlagen: {type(e).__name__}: {e}")
        return None

    best = None
    for rec in recs:
        cand_a, cand_t = _credit(rec), rec.get("title", "")
        sim = (difflib.SequenceMatcher(None, artist.lower(), cand_a.lower()).ratio()
               + difflib.SequenceMatcher(None, title.lower(), cand_t.lower()).ratio()) / 2
        cur = (rec.get("score", 0), sim, cand_a, cand_t)
        if best is None or (cur[0] * cur[1]) > (best[0] * best[1]):
            best = cur
    return best or (0, 0.0, None, None)


def _search_deezer(artist, title):
    def _search(q, limit=5):
        try:
            r = session.get("https://api.deezer.com/search",
                            params={"q": q, "limit": limit}, timeout=10)
            return r.json().get("data", [])
        except requests.RequestException as e:
            print(f"Deezer fehlgeschlagen: {type(e).__name__}: {e}")
            return []

    hits = _search(f'artist:"{artist}" track:"{title}"')
    if not hits:
        hits = _search(f"{artist} {title}")   # toleriert Abweichungen

    best = None
    for t in hits:
        ca, ct = t["artist"]["name"], t["title"]
        sim = (difflib.SequenceMatcher(None, artist.lower(), ca.lower()).ratio()
               + difflib.SequenceMatcher(None, title.lower(), ct.lower()).ratio()) / 2
        if best is None or sim > best[1]:
            best = (100, sim, ca, ct)
    return best or (0, 0.0, None, None)


def _decide(lookup, part_a, part_b, min_score, min_similarity):
    """Prüft beide Reihenfolgen mit der übergebenen Lookup-Funktion."""
    s1, sim1, a1, t1 = lookup(part_a, part_b)
    s2, sim2, a2, t2 = lookup(part_b, part_a)

    if s1 * sim1 >= s2 * sim2:
        status, score, sim, artist, title = "ok", s1, sim1, a1, t1
    else:
        status, score, sim, artist, title = "swapped", s2, sim2, a2, t2

    if score < min_score or sim < min_similarity:
        return Match("unknown", None, None, score, sim)
    return Match(status, artist, title, score, sim)


def similarity_check(artist_, title_, min_score=75, min_similarity=0.55, allow_musicbrainz=False):
    """
    Prüft ob Künstler und Titel existieren und ob sie korrekt zugeordnet sind.
    Dazu wird zuerst bei Deezer abgefragt (schnell, verträgt parallele Anfragen). Wenn das kein
    sicheres Ergebnis liefert, wird optional Musicbrainz als letzte, genauere aber langsame
    Instanz befragt.
    :param artist_: Der zu prüfende Künstler
    :param title_: Der zu prüfende Titel
    :param min_score: Mindestgenauigkeit der Übereinstimmung des Suchtextes und Ergebnisses an. (Musicbrainz-only)
    :param min_similarity: Mindestgenauigkeit der Übereinstimmung des Künstlers/Titels mit artist_/title_
    :param allow_musicbrainz: Erlaubt Musicbrainz als letzte Instanz, wenn Deezer unsicher ist (~30s)
    :return: class Match(status, artist, title, score, similarity)
    """
    match = _decide(_search_deezer, artist_, title_, min_score, min_similarity)
    if match.status != "unknown":
        return match

    if allow_musicbrainz:
        print("Checke Musicbrainz")
        with _mb_lock:
            try:
                return _decide(_search_musicbrainz, artist_, title_, min_score, min_similarity)
            except requests.RequestException:
                return match

    return match