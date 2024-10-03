from pathlib import Path
from google.cloud import speech_v1 as speech
import io
import pickle

datadir = Path(__file__).parents[1] / "data"

# Create a client
client = speech.SpeechClient()

# Path to your audio file
audio_file_path = datadir / "raw" / "sample.wav"

# Read the audio file
with io.open(audio_file_path, "rb") as audio_file:
    content = audio_file.read()

# Configure the audio settings
audio = speech.RecognitionAudio(content=content)
config = speech.RecognitionConfig(
    language_code="en-US",
)

# Perform the transcription
# response = client.recognize(config=config, audio=audio)
with open(datadir / "processed" / "transcription.pkl", "rb") as f:
    response = pickle.load(f)

# Print the transcription results
# with open(datadir / "processed" / "transcription.pkl", "wb") as f:
#     pickle.dump(response, f)

print(response)
