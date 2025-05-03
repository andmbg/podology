# Features to do

- **Diarization**: Lemonfox speaker assignment is imprecise around turn ends. We may have to, instead of taking over 
  Lemonfox's speaker assignment, use the word-level assignments and assign the speaker to the whole turn ourselves.
  - HOWEVER: Check first if word-level assignment is actually better than the turn-level assignment.
- **Ongoing transcription**: We want to see what transcription jobs are still ongoing.
- **Transcription API id**: Add to transcripts the name of the transcriber API, maybe date of transcription. Should be 
  possible to use >1 APIs on one corpus.

## Meta/Download tab:

- **Full show notes**: Show full HTML show notes in or around grid table.
- **Hide EID** from grid table
- **Download Audio**: Issue is if this is global or user-wise - it touches on the whole public aspect of the project
- **Transcribe large episodes**: Download, split and send. LemonFox stops working around 2h duration.
  - **Consequently**, this would be a LemonFox-specific issue. This might have to be handled by the transcriber 
    class. Thinking even further, how transcription is done (Tell API about an mp3 on the web, Download and send mp3)
    seems it has to be transcriber class specific and maybe even open to parameters by the user.

## Transcript/Episode tab:

- Transcript display: Playback if audio present

## Terms tab:

- **Zero point** for episodes with no occurrences in frequency plot
- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

- Show hits in scrollbar
- Metadata AG Grid: multiline display of (title and) show notes.

# Bugs

- When an episode gets transcribed (and indexed and statsed), the plotting function in the same runtime session misses something, probably the current EpisodeStore instance.
  - => we could make the DummyTranscriber a little nicer and copy an existing episode into the transcript (instead of writing just a sentence), so we can also run stats on it.
