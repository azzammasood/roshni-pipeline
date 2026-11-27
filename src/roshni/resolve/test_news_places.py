from roshni.resolve import news_places as np

G = np.gazetteer(
    [("ke_ibc:IBC - Korangi", "IBC - Korangi"), ("ke_ibc:IBC - Landhi", "IBC - Landhi")]
)


def keys(title):
    return [(p["key"], p["method"], p["confidence"]) for p in np.find(title, G)]


def test_exact_names_and_aliases():
    assert keys("MEPCO issues load shedding schedule for city") == [("MEPCO", "exact", 1.0)]
    assert keys("Load-shedding hits Korangi, Landhi in Karachi") == [
        ("ke_ibc:IBC - Korangi", "exact", 1.0),
        ("ke_ibc:IBC - Landhi", "exact", 1.0),
        ("K-Electric", "exact", 1.0),
    ]
    assert keys("Pindi traders protest outages")[0][:2] == ("IESCO", "exact")


def test_near_spellings_keep_their_ratio():
    (p,) = np.find("Power cuts across Rawlpindi", G)
    assert p["key"] == "IESCO" and p["method"] == "fuzzy" and 0.88 <= p["confidence"] < 1


def test_no_false_places():
    assert keys("Governor, Energy Minister discuss load shedding, power issues") == []
    assert keys("Chief Minister expresses concern over unannounced load-shedding") == []
