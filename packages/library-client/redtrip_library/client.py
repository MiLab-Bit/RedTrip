from __future__ import annotations

import http.client
import json
import os
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .endpoints import ENDPOINTS

BASE = "https://data1.library.sh.cn"
SOUYUN = "https://api.sou-yun.cn/open"

DEFAULT_NO_PROXY = (
    "*.library.sh.cn,library.sh.cn,data1.library.sh.cn,"
    "opendata.library.sh.cn,sou-yun.cn,api.sou-yun.cn"
)


@dataclass
class SlcResponse:
    ok: bool
    status: int
    data: Any | None
    text: str | None
    error: str | None = None
    endpoint: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "endpoint": self.endpoint,
            "error": self.error,
            "has_data": self.data is not None,
        }


class SlcClient:
    """HTTP client aligned with SLC MCP (stdio) behavior.

    Network optimization (方案C): each worker thread reuses a persistent
    keep-alive HTTPS connection per host via a thread-local pool, eliminating
    the repeated TLS handshakes that the previous per-call urllib opener paid.
    Falls back to a fresh urllib connection on any transport error.
    """

    def __init__(
        self,
        key: str | None = None,
        *,
        timeout: float = 25.0,
        bypass_proxy: bool = True,
        pool_size: int = 16,
    ) -> None:
        self.key = (key or os.getenv("SLC_API_KEY", "")).strip()
        self.timeout = timeout
        self.pool_size = pool_size
        if bypass_proxy:
            self._ensure_no_proxy()
        # Thread-local keep-alive connection pool (host -> HTTPSConnection).
        self._local = threading.local()
        self._lock = threading.Lock()
        # Legacy opener retained strictly as a fallback channel.
        if bypass_proxy:
            self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        else:
            self._opener = urllib.request.build_opener()

    @staticmethod
    def _ensure_no_proxy() -> None:
        current = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
        merged = ",".join(
            x for x in [current.strip(), DEFAULT_NO_PROXY] if x
        )
        os.environ["NO_PROXY"] = merged
        os.environ["no_proxy"] = merged

    # ---- connection pool (keep-alive) ----

    def _pool(self) -> dict[str, "http.client.HTTPSConnection"]:
        pool = getattr(self._local, "pool", None)
        if pool is None:
            pool = {}
            self._local.pool = pool
        return pool

    def _conn_for(self, host: str) -> "http.client.HTTPSConnection":
        pool = self._pool()
        conn = pool.get(host)
        if conn is None:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, context=ctx, timeout=self.timeout)
            pool[host] = conn
        return conn

    def _drop(self, host: str) -> None:
        pool = self._pool()
        conn = pool.pop(host, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def _http(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        h = {
            "User-Agent": "RedTrip-library-client/0.1",
            "Accept": "application/json",
            "Connection": "keep-alive",
        }
        if headers:
            h.update(headers)
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc
        req_uri = parsed.path + (("?" + parsed.query) if parsed.query else "")
        # Preferred path: reuse a keep-alive connection from the pool.
        try:
            return self._request_once(self._conn_for(host), method, req_uri, data, h, host)
        except (http.client.HTTPException, OSError, ssl.SSLError):
            self._drop(host)
            try:
                return self._request_once(self._conn_for(host), method, req_uri, data, h, host)
            except Exception:  # noqa: BLE001
                return self._http_legacy(method, url, data=data, headers=headers)
        except Exception:  # noqa: BLE001
            return self._http_legacy(method, url, data=data, headers=headers)

    def _request_once(
        self,
        conn: "http.client.HTTPSConnection",
        method: str,
        req_uri: str,
        data: bytes | None,
        headers: dict[str, str],
        host: str,
    ) -> tuple[int, str]:
        conn.request(method, req_uri, body=data, headers=headers)
        resp = conn.getresponse()
        status = resp.status
        text = resp.read().decode("utf-8", "replace")
        # If the server closes the connection, discard it so the next call reconnects.
        if (resp.getheader("Connection") or "").lower() == "close":
            self._drop(host)
        return status, text

    def _http_legacy(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        h = {
            "User-Agent": "RedTrip-library-client/0.1",
            "Accept": "application/json",
        }
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")[:2000]
            except Exception:  # noqa: BLE001
                body = ""
            return e.code, body
        except Exception as e:  # noqa: BLE001
            return 0, repr(e)

    def _wrap(self, status: int, text: str, endpoint: str) -> SlcResponse:
        if status == 0:
            return SlcResponse(
                ok=False,
                status=0,
                data=None,
                text=text,
                error=f"network/tls: {text}",
                endpoint=endpoint,
            )
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            data = None
        ok = 200 <= status < 300
        return SlcResponse(
            ok=ok,
            status=status,
            data=data,
            text=None if data is not None else text[:2000],
            error=None if ok else f"http {status}",
            endpoint=endpoint,
        )

    def call(
        self,
        endpoint_id: str,
        params: dict[str, Any] | None = None,
        path_args: list[Any] | None = None,
        *,
        key: str | None = None,
    ) -> SlcResponse:
        params = dict(params or {})
        path_args = list(path_args or [])
        ep = next((e for e in ENDPOINTS if e["id"] == endpoint_id), None)
        if not ep:
            return SlcResponse(
                ok=False,
                status=404,
                data=None,
                text=None,
                error="unknown endpoint",
                endpoint=endpoint_id,
            )
        try:
            path = ep["path"].format(*path_args) if path_args else ep["path"]
        except Exception as e:  # noqa: BLE001
            return SlcResponse(
                ok=False,
                status=400,
                data=None,
                text=None,
                error=f"path_args: {e}",
                endpoint=endpoint_id,
            )

        base_url = path if path.startswith("http") else BASE + path
        method = str(ep.get("method", "GET")).upper()
        use_key = (key or self.key).strip()
        q = dict(params)
        if ep.get("needs_key"):
            if not use_key:
                return SlcResponse(
                    ok=False,
                    status=400,
                    data=None,
                    text=None,
                    error="missing SLC_API_KEY",
                    endpoint=endpoint_id,
                )
            q["key"] = use_key

        if method == "POST":
            body = json.dumps(params, ensure_ascii=False).encode("utf-8")
            post_url = base_url
            if ep.get("needs_key"):
                post_url += "?" + urllib.parse.urlencode({"key": use_key})
            status, text = self._http(
                "POST",
                post_url,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            return self._wrap(status, text, endpoint_id)

        url = base_url + "?" + urllib.parse.urlencode(q)
        status, text = self._http("GET", url)
        return self._wrap(status, text, endpoint_id)

    # ---- convenience ----

    def building_list(self, freetext: str = "") -> SlcResponse:
        return self.call("building_list", {"freetext": freetext})

    def building_detail(self, uri: str) -> SlcResponse:
        return self.call("building_detail", {"uri": uri})

    def event_list(self, buri: str) -> SlcResponse:
        """Cross-dataset join key path (ASCII buri)."""
        return self.call("event_list", {"buri": buri})

    def road(self, freetext: str = "") -> SlcResponse:
        """路段脉络（漫步的容器层）—— SLC road_list 已有但此前未接入。"""
        return self.call("road_list", {"freetext": freetext})

    def red_event_list(
        self,
        *,
        keyword: str = "",
        date: str = "",
    ) -> SlcResponse:
        # Match MCP server param names (camelCase) which the upstream accepts.
        if keyword:
            params = {"eventFreeText": keyword}
        elif date:
            params = {"eventDate": date}
        else:
            params = {"eventFreeText": ""}
        return self.call("route_getEventList", params)

    def red_event_detail(self, uri: str) -> SlcResponse:
        return self.call("route_getEventDetail", {"uri": uri})

    def poem(self, keyword: str = "", **extra: Any) -> SlcResponse:
        p: dict[str, Any] = {"key": keyword, "jsontype": "true"}
        for k in ("scope", "dynasty", "type", "rhyme", "pageno"):
            if extra.get(k) is not None:
                p[k] = extra[k]
        url = SOUYUN + "/poem?" + urllib.parse.urlencode(p)
        status, text = self._http("GET", url)
        return self._wrap(status, text, "souyun_poem")

    def health_probe(self) -> dict[str, Any]:
        """Lightweight connectivity check used by API /v1/health."""
        result: dict[str, Any] = {
            "key_configured": bool(self.key),
            "bypass_proxy": True,
            "checks": {},
        }
        # Prefer ASCII-friendly list call; empty freetext is OK for probe.
        bl = self.building_list("")
        result["checks"]["building_list"] = bl.summary()
        if bl.ok and isinstance(bl.data, dict):
            uri = _first_building_uri(bl.data)
            result["sample_uri"] = uri
            if uri:
                detail = self.building_detail(uri)
                result["checks"]["building_detail"] = detail.summary()
                events = self.event_list(uri)
                result["checks"]["event_list"] = events.summary()
        else:
            # Fallback probe: red events without Chinese if possible
            re = self.red_event_list(keyword="")
            result["checks"]["route_getEventList"] = re.summary()
        result["ok"] = any(
            c.get("ok") for c in result["checks"].values() if isinstance(c, dict)
        )
        return result


def _first_building_uri(payload: dict[str, Any]) -> str | None:
    """Best-effort extract of a building URI from heterogeneous list payloads."""
    candidates: list[Any] = []
    for key in ("data", "result", "list", "buildings", "items"):
        val = payload.get(key)
        if isinstance(val, list):
            candidates = val
            break
        if isinstance(val, dict):
            for k2 in ("list", "items", "data", "result"):
                if isinstance(val.get(k2), list):
                    candidates = val[k2]
                    break
            if candidates:
                break
    if not candidates and isinstance(payload.get("data"), list):
        candidates = payload["data"]

    for item in candidates[:20]:
        if not isinstance(item, dict):
            continue
        for k in ("uri", "buri", "id", "buildingUri", "building_uri"):
            v = item.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, str) and "/" in v and len(v) > 8:
                return v
    return None
