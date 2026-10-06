import httpx
import pytest

from roshni.fetch.http import FetchRefused, PoliteClient, is_denied_host

UA = "roshni-pipeline/0.1 (+test)"


def make_client(handler, **kw) -> tuple[PoliteClient, list[float]]:
    sleeps: list[float] = []
    t = [0.0]

    def sleep(s: float) -> None:
        sleeps.append(s)
        t[0] += s

    c = PoliteClient(
        UA, transport=httpx.MockTransport(handler), sleep=sleep, clock=lambda: t[0], **kw
    )
    return c, sleeps


@pytest.mark.parametrize(
    "url,denied",
    [
        ("https://www.lesco.gov.pk/x", True),
        ("https://ccms.pitc.com.pk/", True),
        ("https://pitc.com.pk/", True),
        ("https://iesco.com.pk/load-shedding", False),
        ("https://notpitc.com.pk/", False),
    ],
)
def test_denylist(url: str, denied: bool) -> None:
    assert is_denied_host(url) is denied


def test_denied_host_never_requested() -> None:
    calls = []
    c, _ = make_client(lambda r: calls.append(r) or httpx.Response(200))
    with pytest.raises(FetchRefused):
        c.get("https://ccms.pitc.com.pk/anything")
    assert calls == []


def test_robots_disallow_respected_and_cached() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200, text="ok")

    c, _ = make_client(handler)
    assert c.get("https://ke.com.pk/public").text == "ok"
    with pytest.raises(FetchRefused):
        c.get("https://ke.com.pk/private/x")
    assert calls.count("/robots.txt") == 1


def test_user_agent_and_throttle() -> None:
    uas = []

    def handler(req: httpx.Request) -> httpx.Response:
        uas.append(req.headers["user-agent"])
        return httpx.Response(404 if req.url.path == "/robots.txt" else 200)

    c, sleeps = make_client(handler, min_interval=1.0)
    c.get("https://iesco.com.pk/a")
    c.get("https://iesco.com.pk/b")
    assert set(uas) == {UA}
    assert sleeps == [1.0, 1.0]  # robots, a, b: each later request waits a full interval


def test_retries_5xx_then_succeeds() -> None:
    n = {"a": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        n["a"] += 1
        return httpx.Response(503 if n["a"] < 2 else 200)

    c, _ = make_client(handler, min_interval=0)
    assert c.get("https://iesco.com.pk/a").status_code == 200
    assert n["a"] == 2
