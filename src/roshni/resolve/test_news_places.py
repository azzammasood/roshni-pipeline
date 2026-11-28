from roshni.resolve import news_places as np

# K-Electric's IBC names as in dbt/seeds/review_ibc_subdivision.csv.
IBCS = [
    "Bahadurabad", "Baldia", "Bin Qasim", "Clifton", "Defence", "F.B. Area", "Gadap", "Garden",
    "Gulshan", "Johar - I", "Johar - II", "KIMZ", "Korangi", "Landhi", "Layari - I", "Layari - II",
    "Liaqatabad", "Malir", "Nazimabad", "New Karachi", "North Karachi", "North Nazimabad",
    "Orangi - I", "Orangi - II", "SITE", "Saddar", "Shah Faisal", "Surjani", "Tipu Sultan", "Uthal",
]  # fmt: skip
G = np.gazetteer([(f"ke_ibc:IBC - {n}", f"IBC - {n}") for n in IBCS])

# Labelled set. "live": the twelve headlines on the site on 2026-11-28, labelled by Claude.
# "hard": written to test the precision rules (not real headlines).
LABELLED = [
    ("live", "KE’s clarification on excessive load-shedding in Landhi", {"K-Electric", "ke_ibc:IBC - Landhi"}),
    ("live", "KE denies carrying out excessive loadshedding", {"K-Electric"}),
    ("live", "Russian strikes hit two bridges in Kyiv, cause water, power cuts, mayor says", set()),
    ("live", "Small traders assail KE for power outages", {"K-Electric"}),
    ("live", "Leghari agrees to reduce load shedding in high-loss areas of KP", set()),
    ("live", "JI demands KE end unannounced load-shedding in Lyari", {"K-Electric", "ke_ibc:IBC - Layari"}),
    ("live", "'72% of Karachi feeders free of loadshedding'", {"K-Electric"}),
    ("live", "Frequent, prolonged power cuts irk Pindi residents", {"IESCO"}),
    ("live", "Several areas in Karachi gain load-shedding exemption", {"K-Electric"}),
    ("live", "JI protests power outages, inflation in KP", set()),
    ("live", "Govt unveils hi-tech system to manage loadshedding", set()),
    ("live", "Forced loadshedding: ‘New grid stations, additional power transformers needed in Hyderabad’", {"HESCO"}),
    ("hard", "Defence minister briefs parliament on power sector", set()),
    ("hard", "Outages in Defence and Clifton, says KE", {"K-Electric", "ke_ibc:IBC - Defence", "ke_ibc:IBC - Clifton"}),
    ("hard", "Hyderabad, India sees record power demand", set()),
    ("hard", "Rawlpindi traders protest outages", {"IESCO"}),
    ("hard", "Garden party cancelled after rain", set()),
    ("hard", "Power cuts across Gulshan and Johar in Karachi", {"K-Electric", "ke_ibc:IBC - Gulshan", "ke_ibc:IBC - Johar"}),
    ("hard", "LESCO announces new schedule for Lahore", {"LESCO"}),
    ("hard", "Officials say the site of the new grid is ready", set()),
    ("hard", "Keen observers note longer outages in Multan", {"MEPCO"}),
]  # fmt: skip


def keys(title):
    return {p["key"] for p in np.find(title, G)}


def test_labelled_set_precision_and_recall():
    tp = fp = fn = 0
    wrong = []
    for kind, title, want in LABELLED:
        got = keys(title)
        tp, fp, fn = tp + len(got & want), fp + len(got - want), fn + len(want - got)
        if got != want:
            wrong.append((kind, title, sorted(got), sorted(want)))
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    print(f"news places: precision {precision:.2f}, recall {recall:.2f}, {len(LABELLED)} headlines")
    assert precision == 1.0 and recall == 1.0, wrong


def test_near_spellings_keep_their_ratio():
    (p,) = np.find("Power cuts across Rawlpindi", G)
    assert p["key"] == "IESCO" and p["method"] == "fuzzy" and 0.88 <= p["confidence"] < 1


def test_split_ibcs_are_one_place():
    (p,) = [p for p in np.find("Outages in Orangi", G) if p["kind"] == "kelectric_ibc"]
    assert p["label"] == "IBC - Orangi" and p["key"] == "ke_ibc:IBC - Orangi"
