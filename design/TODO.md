# Features to do

- RAG:
  - implement search
  - implement LLM usage
- Audio Playback on clicking on transcript
- term finds as plot next to transcript scrollbar
- click on dot in term plot opens episode

- Writeback: When looking at a transcript, I want to be able to
  - re-label speakers
  - correct mistakes
  - ideally, after correction, aggregate a dataset to fine-tune the Whisper model

## Backend:

- move transcript post-processing into the abstract base transcriber object

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

- Offload embedding to remote API; upgrade API to do SentenceTransformer embeddings and return them.

# Bugs

- failed transcriptions create transcript json files that trip up startup scanning.
- When database-writing operations (like transcript post-processing) are done wholesale with concurrent processing, we get sqlite3 lock errors due to the db being locked on file-level. Writes may have to be queued.
- API has alignment model hardcoded even though some code suggests parameterization.
