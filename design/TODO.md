# Features to do

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- make an abstract renderer class, ticker as implementing it
- dummy video renderer
- make video rendering remote
- second worker queue for video rendering; when transcription is done, place order on video queue

## Meta/Download tab:

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

- Timing:
  - Episodenende:  Video=center, Text=bottom
  - Episodenstart: Video=center, Text=top
- Breitere Zeitrahmen (50-100%)
- lane order: center to margin
- weißer Hintergrund, sichtbare Schatten, sichtbares Glühen
- weiche Frame-Bewegung

# Dysfunction

# Bugs

