# Features to do

- RAG:
  - Transcript tab looks within-episode.
    - next to Transcript or search-hit-col: Prompt relevance as lines (or thin rects);
      you can input up to 10 term searches or prompt searches. Term searches yield term highlights in the transcript and its search-hit-col. Prompt searches yield a line per prompt whose thickness or opacity indicates relevance.
    
    - HOW:
      - add to each segment span the relevance score per prompt
      - redesign Transcript class: per segment, hold start/end, turn membership, chunk membership; output methods use this.

- Audio Playback on clicking on transcript
- click on dot in term plot opens episode

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- move transcript post-processing to the API, make the worker flexible so they can receive a job at any point in the pipeline and do everything downstream

## Meta/Download tab:

- separate cols for each status
- project time to finish for whole podcast using timestamps from processing
- BUG: min size of tooltip is too big, short notes leave empty space
  Ideal: Size of wordcloud + Title + 2-5 lines of notes; click on wordcloud selects episode & transcript tab

## Transcript/Episode tab:

- cleaner speaker display classes
- Hide standard scroll thumb, client-callback highlights currently visible time range in transcript hits plot

## Terms tab:

- Switch between occurrences per 1000 and absolute count on y-axis

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
- when I click a card from the Across tab and in the Within tab delete a tag, the selected episode jumps back to where it was before.