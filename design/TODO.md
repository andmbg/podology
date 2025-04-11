# Features to do

- Lemonfox speaker assignment is imprecise around turn ends. We may have to, instead of taking over Lemonfox's 
  speaker assignment, use the word-level assignments and assign the speaker to the whole turn ourselves.
  - HOWEVER: Check first if word-level assignment is actually better than the turn-level assignment.

- We want to see what transcription jobs are still ongoing.

- Add to transcripts the name of the transcriber API, maybe date of transcription. Should be possible to use >1 APIs 
  on one corpus.

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.



