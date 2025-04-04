from pathlib import Path


"""
Here are some configurations of the machine itself, not of any instantiation in the form
of one podcast or another. This is just to tease out some configurations that would
otherwise be buried in the code.
"""

# Where the store folder is located; typically just one of them:
EPISODE_STORE_PATH = Path("data")

# Styles for speakers in transcript display:
SPEAKER_STYLES = {
    "SPEAKER_00": {"backgroundColor": "#e3f2fd", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_01": {"backgroundColor": "#fff3e0", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_02": {"backgroundColor": "#ffebee", "borderRadius": "4px", "padding": "8px"},
    "SPEAKER_03": {"backgroundColor": "#f1f8e9", "borderRadius": "4px", "padding": "8px"},
}
