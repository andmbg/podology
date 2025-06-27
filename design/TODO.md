# Features to do

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- move transcript post-processing into the abstract base transcriber object
- turn the transcription API to a download link output type

### data structures

- Episode
  - ProcessStatus
    - audio
    - transcript
    - wordcloud
    - scrollvid
    - job-id (do we need queue id?)

### Episode & postprocess

post_process(store, [episodes])

vs

episode.post_process()

## Meta/Download tab:

- separate cols for each status

## Transcript/Episode tab:

- Transcript display: Playback if audio present
- Show hits in scrollbar

### Animated Word Ticker

- Tighter coupling

## Terms tab:

- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

- Das Ticker-Objekt, das in Blender reingeht sollte eine einfache (JSON-)Datenstruktur sein, die keine Abhängigkeiten mitbringt. Derzeit wird zB numpy benötigt und das wollen wir nicht noch im Blender-python installieren.

- Timing:
  - Episodenende:  Video=center, Text=bottom
  - Episodenstart: Video=center, Text=top
- Breitere Zeitrahmen (50-100%)
- lane order: center to margin
- weißer Hintergrund, sichtbare Schatten, sichtbares Glühen
- weiche Frame-Bewegung

# Dysfunction

# Bugs

- HF api key needs to go to the transcriber, not the main project

