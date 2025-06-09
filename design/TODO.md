# Features to do

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Meta/Download tab:

- add wordcloud to tooltip, click on tooltip takes to transcript, click on row heightens row, you see description and wordcloud or so

## Transcript/Episode tab:

- Transcript display: Playback if audio present
- Show hits in scrollbar

### Animated Word Cloud ("Word Weather")

- Discussed in notebook 2.01

## Terms tab:

- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

# Dysfunction

# Bugs

