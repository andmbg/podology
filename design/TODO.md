# Features to do

- RAG and layout:
  - Transcript tab looks within-episode.
    - left of transcript: Prompt relevance
    - [DONE] **right of transcript (close to scrollbar): word finds** <= imminent
  - Plot tab looks across episodes.
    - plot 1: terms
    - plot 2: prompt => per-episode average relevance
      - click on episode: add time-series of chunks to transcript, move to transcript tab

- Audio Playback on clicking on transcript
- click on dot in term plot opens episode

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- move transcript post-processing into the abstract base transcriber object

## Meta/Download tab:

- separate cols for each status
- project time to finish for whole podcast using timestamps from processing
- BUG: min size of tooltip is too big, short notes leave empty space
  Ideal: Size of wordcloud + Title + 2-5 lines of notes; click on wordcloud selects episode & transcript tab

## Transcript/Episode tab:

- cleaner speaker display classes
- Hide standard scroll thumb, client-callback highlights currently visible time range in transcript hits plot

## Terms tab:

- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

- in dev, the download table still shows the real project


# Bugs

- failed transcriptions create transcript json files that trip up startup scanning.
- When database-writing operations (like transcript post-processing) are done wholesale with concurrent processing, we get sqlite3 lock errors due to the db being locked on file-level. Writes may have to be queued.
- API has alignment model hardcoded even though some code suggests parameterization.
- if one search term contains another, highlights in the transcript get messed up.
- if a search term has spaces in it, it is not marked in the vertical search hit column.
