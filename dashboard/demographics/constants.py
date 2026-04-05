"""Constants for the demographics dashboard feature."""

DEMOGRAPHICS_ACTIVE_KEY = "demographics"
DEMOGRAPHICS_PAGE_TITLE = "Demographic Dashboard"
DEMOGRAPHIC_SUMMARY_CARD_SPECS = [
    {"key": "students", "label": "Students", "tone": "default"},
    {"key": "male", "label": "Male", "tone": "default"},
    {"key": "female", "label": "Female", "tone": "default"},
    {"key": "birth_locations", "label": "Birth Locations", "tone": "default"},
]

# Approximate Zimbabwe location anchors used by the origin map.
# These are intentionally lightweight city/district reference points rather than
# survey-grade coordinates, but they place the cohort on a real interactive map.
BIRTH_LOCATION_MAP_POINTS = {
    "beitbridge": {"lng": 30.00, "lat": -22.22, "province": "Matabeleland South"},
    "bindura": {"lng": 31.33, "lat": -17.30, "province": "Mashonaland Central"},
    "buhera": {"lng": 31.90, "lat": -19.20, "province": "Manicaland"},
    "bulawayo": {"lng": 28.58, "lat": -20.15, "province": "Bulawayo"},
    "chegutu": {"lng": 30.14, "lat": -18.13, "province": "Mashonaland West"},
    "chikomba": {"lng": 31.90, "lat": -19.00, "province": "Mashonaland East"},
    "chimanimani": {"lng": 32.86, "lat": -19.80, "province": "Manicaland"},
    "chipinge": {"lng": 32.62, "lat": -20.18, "province": "Manicaland"},
    "chinhoyi": {"lng": 30.20, "lat": -17.37, "province": "Mashonaland West"},
    "chiredzi": {"lng": 31.66, "lat": -21.05, "province": "Masvingo"},
    "gokwe": {"lng": 28.93, "lat": -18.21, "province": "Midlands"},
    "gwanda": {"lng": 29.01, "lat": -20.93, "province": "Matabeleland South"},
    "gweru": {"lng": 29.82, "lat": -19.45, "province": "Midlands"},
    "harare": {"lng": 31.05, "lat": -17.83, "province": "Harare"},
    "hwange": {"lng": 26.50, "lat": -18.36, "province": "Matabeleland North"},
    "kadoma": {"lng": 29.91, "lat": -18.33, "province": "Mashonaland West"},
    "kariba": {"lng": 28.80, "lat": -16.52, "province": "Mashonaland West"},
    "kwekwe": {"lng": 29.81, "lat": -18.93, "province": "Midlands"},
    "lupane": {"lng": 27.80, "lat": -18.93, "province": "Matabeleland North"},
    "makoni": {"lng": 32.15, "lat": -18.70, "province": "Manicaland"},
    "marondera": {"lng": 31.55, "lat": -18.18, "province": "Mashonaland East"},
    "masvingo": {"lng": 30.83, "lat": -20.07, "province": "Masvingo"},
    "mberengwa": {"lng": 29.93, "lat": -20.49, "province": "Midlands"},
    "murewa": {"lng": 31.78, "lat": -17.65, "province": "Mashonaland East"},
    "mutare": {"lng": 32.67, "lat": -18.97, "province": "Manicaland"},
    "mutasa": {"lng": 32.65, "lat": -18.43, "province": "Manicaland"},
    "mutoko": {"lng": 32.23, "lat": -17.40, "province": "Mashonaland East"},
    "nyanga": {"lng": 32.75, "lat": -18.22, "province": "Manicaland"},
    "norton": {"lng": 30.70, "lat": -17.88, "province": "Mashonaland West"},
    "plumtree": {"lng": 27.80, "lat": -20.48, "province": "Matabeleland South"},
    "rusape": {"lng": 32.13, "lat": -18.53, "province": "Manicaland"},
    "shurugwi": {"lng": 30.00, "lat": -19.67, "province": "Midlands"},
    "victoria falls": {"lng": 25.85, "lat": -17.93, "province": "Matabeleland North"},
    "zvishavane": {"lng": 30.07, "lat": -20.33, "province": "Midlands"},
}

BIRTH_LOCATION_MAP_ALIASES = {
    "harare urban": "harare",
    "harare rural": "harare",
    "mutare urban": "mutare",
    "mutare rural": "mutare",
    "bulawayo urban": "bulawayo",
    "bulawayo rural": "bulawayo",
    "makoni district": "makoni",
    "mutasa district": "mutasa",
    "buhera district": "buhera",
    "chipinge district": "chipinge",
    "chimanimani district": "chimanimani",
}
