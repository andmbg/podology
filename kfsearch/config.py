from pathlib import Path


# Where the store folder is located; typically just one of them:
EPISODE_STORE_PATH = Path("data")
EPSTORE_RAW_PATH = Path("data") / "raw"
EPSTORE_PROCESSED_PATH = Path("data") / "processed"

# Styles for speakers in transcript display:
SPEAKER_STYLES = {
    "SPEAKER_00": {"backgroundColor": "#e3f2fd", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_01": {"backgroundColor": "#fff3e0", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_02": {"backgroundColor": "#ffebee", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_03": {"backgroundColor": "#f1f8e9", "borderRadius": "4px", "padding": "8px"},
}
