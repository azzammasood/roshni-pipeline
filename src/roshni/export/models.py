"""Versioned static export documents. JSON Schemas in schemas/v1/ are generated from these models
(`roshni export --write-schemas`) and a test fails if the committed schemas drift."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 1.1.0: DarkProfile.daily_windows; 1.2.0: match review, release month; 1.3.0: national and news
# documents; 1.4.0: national month-by-month series; 1.5.0: K-Electric months from every schedule
# version (MonthlyKeSchedule.changed_in_month); 1.6.0: maintenance (and notices) documents;
# 1.7.0: notices document removed (the pipeline only keeps fully automated sources)
SCHEMA_VERSION = "1.7.0"
LABEL = "Scheduled (published schedule data), not measured outages"
NATIONAL_LABEL = (
    "Load-shedding hours as reported to NEPRA by each distribution company, not measured outages"
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Envelope[T](Strict):
    schema_id: str = Field(description="Document type and major version, e.g. roshni/feeders/v1")
    schema_version: str = Field(description="Semantic version of the document schema")
    generated_at: datetime = Field(description="When this export was produced (UTC)")
    last_updated: datetime = Field(description="Latest source fetch or warehouse build (UTC)")
    label: str = Field(
        description="What the numbers are: schedules, or figures reported to the regulator; "
        "never measurements"
    )
    data: T


class SourceInfo(Strict):
    source: str
    source_file: str
    effective_from: date
    effective_basis: str
    published_label: str | None


class Meta(Strict):
    timezone_display: Literal["Asia/Karachi"]
    utc_offset_hours: Literal[5]
    documents: list[str]
    sources: list[SourceInfo]
    attribution: list[str]
    disclaimer: str


ReviewedBy = Literal["rules", "llm", "claude", "owner"]


class MatchReview(Strict):
    """Why an approximate match was accepted (from the review seed's note; since 1.2.0)."""

    method: Literal["exact", "fuzzy"] = Field(
        description="exact: identical after normalising; fuzzy: name-similarity score below 100"
    )
    reviewed_by: ReviewedBy | None = Field(
        description="rules (autoreview.py), llm (OpenRouter), claude, owner; null if automatic"
    )
    reviewed_on: date | None
    reason: str | None


class LocalityMatch(Strict):
    area_id: str
    area_name: str
    match_status: Literal["auto_exact", "accepted"]
    match_confidence: float = Field(ge=0, le=1)
    review: MatchReview | None = None


class Feeder(Strict):
    feeder_id: str
    source: Literal["iesco", "kelectric"]
    name: str
    feeder_code: str | None
    circle: str | None
    grid: str | None
    ibc: str | None
    category: Literal["Medium", "High", "Very High"] | None
    atc_loss_pct: float | None
    in_feeder_list: bool | None
    has_schedule: bool
    schedule_match_method: str | None
    schedule_match_confidence: float | None
    localities: list[LocalityMatch]


class Window(Strict):
    start_min: int = Field(
        ge=0, le=1439, description="Local (Asia/Karachi) minute of day, inclusive"
    )
    end_min: int = Field(
        ge=1, le=1440, description="Local minute of day, exclusive; end <= start wraps midnight"
    )


class DarkProfile(Strict):
    feeder_id: str
    source: Literal["iesco", "kelectric"]
    effective_from: date
    daily: list[int] | None = Field(
        description="K-Electric: scheduled dark minutes in each local hour 0-23", default=None
    )
    daily_windows: list[Window] | None = Field(
        description="K-Electric: exact scheduled windows behind `daily` (since 1.1.0)", default=None
    )
    scenario_levels: dict[str, list[int]] | None = Field(
        description="IESCO: per interruption level ('2'..'12'), dark minutes in each local hour "
        "0-23 IF that level is active (the files never say which level applies). IESCO slots are "
        "whole local hours (checked at export), so each value is 0 or 60 and exact",
        default=None,
    )


class PlannedShutdown(Strict):
    shutdown_id: str
    release_no: str | None
    release_period: str | None = Field(
        default=None, description="Month of the press release as printed, MM/YYYY (since 1.2.0)"
    )
    outage_date: date
    start_utc: datetime
    end_utc: datetime
    start_local: str
    end_local: str
    circle_as_printed: str
    feeder_name_as_printed: str
    feeder_id: str | None
    feeder_match_state: Literal["matched", "pending_review", "unmatched", "out_of_scope"]
    match_confidence: float | None
    match_review: MatchReview | None = None
    flags: str


class Area(Strict):
    area_id: str
    name: str
    level: str
    province: str
    district: str
    pop_total: float | None
    literacy_pct: float | None
    degree_share_pct: float | None
    pacca_share_pct: float | None
    electricity_share_pct: float | None
    avg_household_size: float | None


class IbcEquity(Strict):
    ibc: str
    listed_feeders: int
    scheduled_feeders: int
    feeders_12h: int
    feeders_6h: int
    share_12h_pct: float | None
    mean_scheduled_hours: float | None
    feeders_with_loss: int
    mean_atc_loss_pct: float | None
    census_subdivision: str | None


class SubdivisionEquity(Strict):
    subdivision_area_id: str
    subdivision_name: str
    ibcs: int
    scheduled_feeders: int
    share_12h_pct: float
    mean_scheduled_hours: float
    literacy_pct: float | None
    degree_share_pct: float | None
    pacca_share_pct: float | None
    avg_household_size: float | None


class Correlation(Strict):
    unit: Literal["subdivision", "feeder"]
    y_name: str
    x_name: str
    n: int
    spearman_rho: float | None


class Anomaly(Strict):
    rule: str
    description: str
    feeders: int


class ReportFact(Strict):
    id: str
    value: float | int | str
    unit: str
    query_id: str


class Report(Strict):
    iso_week: str
    engine: str
    narrative: str
    facts: list[ReportFact]


class OutageBand(Strict):
    band: str = Field(description="Average daily outage band as printed by NEPRA, e.g. 10:00-12:00")
    lower_minutes: int
    upper_minutes: int | None
    feeders: int
    consumers: int
    pct_feeders: float = Field(description="As printed by NEPRA")
    pct_consumers: float
    above_schedule: bool = Field(description="Band starts at or above the category's schedule")


class ReviewCategory(Strict):
    category: str = Field(description="K-Electric loss category as printed (e.g. High Loss)")
    feeders: int
    consumers: int
    avg_atc_loss_pct: int
    scheduled_hours_per_day: float = Field(description="K-Electric's own schedule for the category")
    pct_feeders_above_schedule: float = Field(
        description="Sum of NEPRA's printed band shares at or above the schedule"
    )
    bands: list[OutageBand]


class RegulatorReview(Strict):
    order_date: date
    source_file: str
    source_url: str = Field(description="The order on nepra.org.pk (from config/sources.yml)")
    basis: str
    categories: list[ReviewCategory]


class Equity(Strict):
    scope_note: str
    ibc: list[IbcEquity]
    subdivisions: list[SubdivisionEquity]
    correlations: list[Correlation]
    anomalies: list[Anomaly]
    report: Report | None
    regulator_review: RegulatorReview | None = Field(
        default=None, description="NEPRA's order on K-Electric: outage bands from K-Electric data"
    )


class ReportedHours(Strict):
    company: str = Field(description="Distribution company as printed by NEPRA, e.g. PESCO")
    fiscal_year: str = Field(description="Pakistan fiscal year, July-June, e.g. 2024-25")
    reported_hours_per_day: float = Field(
        description="Average daily load-shedding hours the company reported to NEPRA"
    )
    chosen_report_year: str = Field(description="Report the value comes from (earliest listing)")
    reports: int = Field(description="Number of NEPRA reports that list this company and year")
    min_reported: float
    max_reported: float
    values_disagree: bool = Field(description="Reports differ by more than 0.01 h (flagged)")


class NepraReport(Strict):
    report_year: str
    source_file: str


class PolicyEvent(Strict):
    id: str
    date: date
    summary: str
    max_hours: float | None
    source_url: str


class CircleMonth(Strict):
    circle: str = Field(description="IESCO circle as printed in the press releases")
    windows: int
    window_hours: float


class MonthlyShutdowns(Strict):
    month: str = Field(description="YYYY-MM (Asia/Karachi outage dates as printed)")
    windows: int = Field(description="Planned-shutdown windows announced for the month")
    window_hours: float = Field(description="Sum of window lengths, one per feeder window")
    releases: int
    first_date: date = Field(description="First outage date in the collected releases")
    last_date: date = Field(description="Last outage date in the collected releases")
    circles: list[CircleMonth]


class MonthlyKeSchedule(Strict):
    month: str
    avg_scheduled_hours: float = Field(
        description="Average scheduled hours a day across the feeders in the schedule in force"
    )
    feeders: int
    effective_from: date = Field(description="The schedule in force, effective from this date")
    changed_in_month: bool = Field(
        default=False,
        description="A new schedule took effect during the month (value at month end)",
    )


class MaintenanceMonth(Strict):
    month: str = Field(description="YYYY-MM (Asia/Karachi dates as printed)")
    item: str = Field(description="Listing-page row: a circle, gso or construction")
    windows: int
    feeders: int = Field(description="Distinct feeders (code, else printed name)")
    window_hours: float = Field(description="Sum of window lengths, one per feeder window")
    unique_windows: int = Field(
        description="Windows not already printed in a circle's file (GSO repeats removed)"
    )
    unique_window_hours: float = Field(description="Hours of unique_windows; adds up across rows")
    first_date: date
    last_date: date


class MaintenanceWindow(Strict):
    """One announced IESCO maintenance window (since 1.6.0). Not load shedding."""

    window_id: str
    item: str
    feeder_id: str | None = Field(description="dim_feeder id when the printed code matches")
    feeder_code: str | None
    feeder_name_as_printed: str | None
    grid_as_printed: str | None
    outage_date: date
    start_local: str
    end_local: str
    start_utc: datetime
    end_utc: datetime
    purpose: str | None
    area_affected: str | None
    repeats_circle_window: bool = Field(
        description="A GSO row repeating a window that a circle's file also prints"
    )
    flags: str


class National(Strict):
    basis: str
    caveat: str
    gaps: list[str]
    series: list[ReportedHours]
    reports: list[NepraReport]
    events: list[PolicyEvent]
    monthly_shutdowns: list[MonthlyShutdowns] = Field(
        default_factory=list,
        description="IESCO planned shutdowns per month (announced maintenance, not load shedding)",
    )
    monthly_ke: list[MonthlyKeSchedule] = Field(
        default_factory=list,
        description="K-Electric's published schedule per month, from its effective date only",
    )
    monthly_maintenance: list[MaintenanceMonth] = Field(
        default_factory=list,
        description="IESCO announced maintenance per month and listing row (since 1.6.0)",
    )
    as_of: date | None = Field(default=None, description="Karachi date of this build")


NEWS_LABEL = "Headlines as published by each outlet, linked to the original; not Roshni's reporting"


class NewsHeadline(Strict):
    outlet: str
    title: str = Field(description="Headline exactly as the outlet's feed published it")
    link: str
    published_at: datetime | None = Field(description="Publication time from the feed (UTC)")
    first_seen_at: datetime | None = Field(description="When Roshni's daily fetch first saw it")


DOCUMENTS: dict[str, type] = {
    "meta": Envelope[Meta],
    "feeders": Envelope[list[Feeder]],
    "dark_profiles": Envelope[list[DarkProfile]],
    "planned_shutdowns": Envelope[list[PlannedShutdown]],
    "areas": Envelope[list[Area]],
    "equity": Envelope[Equity],
    "national": Envelope[National],
    "news": Envelope[list[NewsHeadline]],
    "maintenance": Envelope[list[MaintenanceWindow]],
}
