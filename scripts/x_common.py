"""Shared helpers for the 信源 (X sources) channel."""
import datetime as dt, glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config", "x_sources.json")
XDATA = os.path.join(ROOT, "data", "x")
STATE = os.path.join(ROOT, "state", "x_state.json")
TZ = dt.timezone(dt.timedelta(hours=8))  # site dates are Asia/Shanghai

def load_config(): return json.load(open(CONFIG, encoding="utf-8"))
def shanghai_dt(iso): return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
def shanghai_date(iso): return shanghai_dt(iso).date().isoformat()
def load_json_any(f):
    s = open(f, encoding="utf-8").read(); return json.loads(s[s.index("{"):s.rindex("}") + 1])
def day_files(): return sorted(glob.glob(os.path.join(XDATA, "????-??-??.json")))
def known_ids():
    ids = set()
    for f in day_files():
        for it in json.load(open(f, encoding="utf-8"))["items"]: ids.add(it["post_id"])
    return ids
def last_seen():
    """{handle: max post_id} from data/x (authoritative) merged with state file."""
    out = {}
    try: out.update({k: str(v) for k, v in json.load(open(STATE))["last_seen_id"].items()})
    except Exception: pass
    for f in day_files():
        for it in json.load(open(f, encoding="utf-8"))["items"]:
            if int(it["post_id"]) > int(out.get(it["source"], "0")): out[it["source"]] = it["post_id"]
    return out
