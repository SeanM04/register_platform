"""Feature-local constants for the risk dashboard."""

RISK_ACTIVE_KEY = "risk"
RISK_PAGE_TITLE = "Risk Dashboard"

RISK_SUMMARY_CARD_SPECS = [
    {"key": "at_risk_students", "label": "At Risk Students", "tone": "danger"},
    {"key": "high_risk", "label": "High Risk", "tone": "danger"},
    {"key": "medium_risk", "label": "Medium Risk", "tone": "default"},
    {"key": "multi_fail", "label": "2+ Failed Modules", "tone": "default"},
]

HIGH_RISK_DECISIONS = {
    "retake",
    "repeat",
    "fail",
    "failed",
    "excluded",
    "withdrawn",
    "dropped",
    "dropout",
    "suspended",
    "stopped",
}

RISK_PRIORITY = {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2}

RISK_BAND_DEFINITIONS = (
    {"key": "critical", "label": "Critical (6+)", "min_score": 6, "max_score": None, "tone": "critical"},
    {"key": "high", "label": "High (4-5)", "min_score": 4, "max_score": 5, "tone": "high"},
    {"key": "moderate", "label": "Moderate (2-3)", "min_score": 2, "max_score": 3, "tone": "moderate"},
    {"key": "low", "label": "Low (0-1)", "min_score": 0, "max_score": 1, "tone": "low"},
)

RISK_DRIVER_LABELS = {
    "average_below_50": "Average below 50%",
    "average_below_60": "Average 50-59%",
    "failed_3_plus": "3+ failed modules",
    "failed_2": "2 failed modules",
    "failed_1": "1 failed module",
    "carrying_multi": "2+ carried modules",
    "carrying_1": "1 carried module",
    "decision_alert": "Adverse decision",
}

RISK_DRIVER_PRIORITY = {
    "average_below_50": 0,
    "failed_3_plus": 1,
    "decision_alert": 2,
    "failed_2": 3,
    "carrying_multi": 4,
    "average_below_60": 5,
    "failed_1": 6,
    "carrying_1": 7,
}
