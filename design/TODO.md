# Features to do

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- move transcript post-processing into the abstract base transcriber object
- turn the transcription API to a download link output type; not answering by just sending json text in response => consistency

### data structures

- Episode
  - ProcessStatus
    - audio
    - transcript
    - wordcloud
    - scrollvid
    - job-id (do we need queue id?)

## Meta/Download tab:

- separate cols for each status

## Transcript/Episode tab:

- Show hits in scrollbar
- Transcript display: Playback on click on turn, highlight current turn

## Terms tab:

- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

- episode status is DONE already after transcription/stats

- Timing:
  - Episodenende:  Video=center, Text=bottom
  - Episodenstart: Video=center, Text=top
- lane order: center to margin
- weißer Hintergrund, sichtbare Schatten, sichtbares Glühen

# Bugs


