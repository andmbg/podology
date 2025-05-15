# Features to do

- **Diarization**: Lemonfox speaker assignment is imprecise around turn ends. We may have to, instead of taking over 
  Lemonfox's speaker assignment, use the word-level assignments and assign the speaker to the whole turn ourselves.
  - HOWEVER: Check first if word-level assignment is actually better than the turn-level assignment.
- **Ongoing transcription**: We want to see what transcription jobs are still ongoing.
- **Transcription API id**: Add to transcripts the name of the transcriber API, maybe date of transcription. Should be 
  possible to use >1 APIs on one corpus.
- Refine config.ADDITIONAL_STOPWORDS; also, give room for a custom list;

## Meta/Download tab:

- **Download Audio**: Issue is if this is global or user-wise - it touches on the whole public aspect of the project
- **Transcribe large episodes**: Download, split and send. LemonFox stops working around 2h duration.
  - **Consequently**, this would be a LemonFox-specific issue. This might have to be handled by the transcriber 
    class. Thinking even further, how transcription is done (Tell API about an mp3 on the web, Download and send mp3)
    seems it has to be transcriber class specific and maybe even open to parameters by the user.
- Remove description column; add download audio column; add wordcloud to tooltip, click on tooltip takes to transcript, click on row heightens row, you see description and wordcloud or so

## Transcript/Episode tab:

- Transcript display: Playback if audio present
  - Figure out if we have something better that named entities
- Show hits in scrollbar
- move results list to terms tab

### Animated Word Cloud

Next to the transcript, display an animation whose frame is linked to the scroll position of the transcript. The content is the keywords (named entities or topics) that are prevalent around the scroll position. Terms over time appear and disappear in animations like envelopes on alpha and blur. Repetitions of a term close to each other are pooled in one displayed term that stays for longer and/or has greater size/opacity/...

- pixel height of transcript box is ca. 600 - 1100. Video linked to scroll means ca. 1100 frames, = 44 sec of video; => Easy.
- moving window:
  - vertical measure is transcript words
  - Y = scroll position, 0..1000 (frames)
    Die Scrollposition kommt aus dem HTML-Dokument und wird auf 1000 standardisiert.
  - window MIN/MAX = [Y - .5 * WIDTH, Y + .5 * WIDTH]
    Die Fensterposition hängt an der Scrollposition. Der Scrollpunkt liegt in der Fenstermitte, außer am Anfang und Ende.
  - WIDTH = params.winWordCount * script.wordsPerNE
    Das Fenster ist so viele Transkript-Wörter breit, dass im Durchschnitt dieser Episode ca. params.winWordCount (z.B. 30) NE darin landen.
  - 


## Terms tab:

- Remove plot when the last term gets deleted

---

# Features NOT to do

- After a startup that creates the search index but doesn't fill it for some reason, currently, a startup sees the 
  index and doesn't question its completeness. We need to implement a check that verifies the index's completeness 
  and triggers a reindex if necessary.  
  - > Too much work for a very edge case. We can live with that.
  
# IMMINENT

# Bugs

- When an episode gets transcribed (and indexed and statsed), the plotting function in the same runtime session misses something, probably the current EpisodeStore instance.
  - => we could make the DummyTranscriber a little nicer and copy an existing episode into the transcript (instead of writing just a sentence), so we can also run stats on it.
