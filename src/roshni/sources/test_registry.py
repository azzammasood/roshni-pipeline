from roshni.fetch.http import is_denied_host
from roshni.sources.registry import load_registry


def test_repo_registry_loads_and_is_safe() -> None:
    reg = load_registry()
    assert set(reg.sources) == {
        "iesco_schedule_xlsx",
        "iesco_press_release",
        "kelectric_feeder_list",
        "kelectric_schedule",
        # Owner approval 2026-10-13 (DECISIONS.md): national context and news headlines.
        "nepra_per_distribution",
        "news_dawn",
        "news_brecorder",
        "news_tribune",
        "news_app",
        # Owner approval 2026-10-14: category and topic feeds of the same four outlets.
        "news_dawn_business",
        "news_dawn_pakistan",
        "news_brecorder_business",
        "news_brecorder_pakistan",
        "news_tribune_business",
        "news_tribune_pakistan",
        "news_tribune_load_shedding",
        "news_app_business",
        "news_app_tag_load_shedding",
        "news_app_tag_loadshedding",
        # Owner approval 2026-10-13 (N4): NEPRA's 2026-08-31 order on K-Electric.
        "nepra_ke_order",
    }
    assert reg.min_request_interval_seconds >= 1.0
    assert reg.user_agent.startswith("roshni-pipeline/0.1 (+")
    assert len(reg.sources["iesco_schedule_xlsx"].circles or {}) == 6
    for s in reg.sources.values():
        for url in (s.url, s.listing_url):
            assert url is None or not is_denied_host(url)
