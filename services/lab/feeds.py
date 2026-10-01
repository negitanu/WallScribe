"""Bounded public intelligence fetch. No user URL, redirects or config transmission."""

import csv
import io
import json
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCES = {
    "cisa-kev": (
        "CISA KEV",
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
    ),
    "feodo": ("Feodo Tracker C2", "https://feodotracker.abuse.ch/downloads/ipblocklist.csv"),
}
MAX_BYTES = 5 * 1024 * 1024
MAX_FETCH_SECONDS = 8
_fetch_locks = {key: threading.Lock() for key in SOURCES}
_lock = threading.Lock()
_cache = {}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Feed のリダイレクトは許可していません")


def parse_feed(key, raw):
    if key == "cisa-kev":
        doc = json.loads(raw)
        rows = doc.get("vulnerabilities")
        if not isinstance(rows, list) or len(rows) > 20000:
            raise ValueError("KEV Feed の形式または件数が不正です")
        items = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("KEV Feed のレコードが不正です")
            if not isinstance(row.get("cveID"), str):
                continue
            items.append(
                {
                    k: str(row.get(k, ""))[:1000]
                    for k in (
                        "cveID",
                        "vendorProject",
                        "product",
                        "vulnerabilityName",
                        "dateAdded",
                        "knownRansomwareCampaignUse",
                        "requiredAction",
                    )
                }
            )
        items.sort(key=lambda r: r["dateAdded"], reverse=True)
        return items[:100], str(doc.get("dateReleased", ""))[:100]
    if key == "feodo":
        rows = csv.DictReader(
            io.StringIO("\n".join(line for line in raw.splitlines() if not line.startswith("#")))
        )
        items = []
        for index, row in enumerate(rows):
            if index >= 20000:
                raise ValueError("C2 Feed の件数が上限を超えました")
            try:
                ip = ip_address(row.get("dst_ip", ""))
                port = int(row.get("dst_port", "0"))
                if not ip.is_global or not 1 <= port <= 65535 or row.get("c2_status") != "online":
                    continue
                last_online = datetime.strptime(
                    row.get("last_online", "")[:10], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_online > timedelta(days=30):
                    continue
                items.append(
                    {
                        "ip": str(ip),
                        "port": port,
                        "malware": row.get("malware", "")[:100],
                        "last_online": row.get("last_online", "")[:100],
                    }
                )
            except ValueError:
                continue
        return items[:100], ""
    raise ValueError("未知の Feed")


def _read_bounded(response, deadline):
    chunks, size = [], 0
    # HTTPResponse.read1 performs at most one underlying read. read(n) can keep
    # accepting a slow stream forever despite a per-socket inactivity timeout.
    read = getattr(response, "read1", response.read)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Feed の取得時間が上限を超えました")
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            sock.settimeout(remaining)
        chunk = read(min(65536, MAX_BYTES + 1 - size))
        if time.monotonic() > deadline:
            raise TimeoutError("Feed の取得時間が上限を超えました")
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("Feed サイズの上限を超えました")
        chunks.append(chunk)


def fetch_feed(key, opener=None):
    if key not in SOURCES:
        raise ValueError("登録されていない Feed です")
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached["stamp"] < 900:
            return deepcopy(cached["data"]) | {"cached": True}
    name, url = SOURCES[key]

    def failure():
        # Never label old data as current or pass remote error content through.
        return {
            "key": key,
            "name": name,
            "url": url,
            "status": "error",
            "error": "Feed を取得・検証できませんでした。接続環境と配信元を確認してください。",
            "items": [],
            "fetched_at": None,
            "last_success_at": cached["data"]["fetched_at"] if cached else None,
        }

    # At most one fetch per fixed source; stalled network I/O cannot block
    # snapshots or the other source and cannot accumulate fetch workers.
    if not _fetch_locks[key].acquire(blocking=False):
        return failure()
    deadline = time.monotonic() + MAX_FETCH_SECONDS
    finished = threading.Event()
    result = {}

    def download():
        try:
            client = opener or build_opener(NoRedirect())
            with client.open(
                Request(
                    url,
                    headers={
                        "User-Agent": "WallScribe/1.2 threat-assist",
                        "Accept": "application/json,text/csv",
                    },
                ),
                timeout=MAX_FETCH_SECONDS,
            ) as response:
                raw = _read_bounded(response, deadline)
            items, published = parse_feed(key, raw.decode("utf-8-sig"))
            data = {
                "key": key,
                "name": name,
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "published_at": published,
                "items": items,
                "status": "ok",
                "cached": False,
            }
            with _lock:
                # A timed-out worker must not later publish its response as fresh.
                if time.monotonic() > deadline:
                    raise TimeoutError("Feed の取得時間が上限を超えました")
                _cache[key] = {"stamp": time.monotonic(), "data": data}
            result["data"] = data
        except Exception:
            pass
        finally:
            # Keep the source occupied until the actual worker ends, including
            # DNS/header reads whose inactivity timeout may not bound wall time.
            _fetch_locks[key].release()
            finished.set()

    worker = threading.Thread(target=download, name="wallscribe-feed-" + key, daemon=True)
    try:
        worker.start()
    except Exception:
        _fetch_locks[key].release()
        return failure()
    if not finished.wait(max(0, deadline - time.monotonic())):
        return failure()
    return deepcopy(result["data"]) if "data" in result else failure()


def snapshots():
    with _lock:
        now = time.monotonic()
        return [deepcopy(v["data"]) | {"stale": now - v["stamp"] >= 86400} for v in _cache.values()]
