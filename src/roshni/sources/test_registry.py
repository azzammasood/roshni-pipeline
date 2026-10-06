from roshni.fetch.http import is_denied_host
from roshni.sources.registry import load_registry


def test_repo_registry_loads_and_is_safe() -> None:
    reg = load_registry()
    assert set(reg.sources) == {
        "iesco_schedule_xlsx",
        "iesco_press_release",
        "kelectric_feeder_list",
        "kelectric_schedule",
    }
    assert reg.min_request_interval_seconds >= 1.0
    assert reg.user_agent.startswith("roshni-pipeline/0.1 (+")
    assert len(reg.sources["iesco_schedule_xlsx"].circles or {}) == 6
    for s in reg.sources.values():
        for url in (s.url, s.listing_url):
            assert url is None or not is_denied_host(url)
