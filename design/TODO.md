# Features to do

- **Diarization**: imprecise diarization from whisper - ways to improve, or correct in the frontend
- **Ongoing transcription**: We want to see what transcription jobs are still ongoing.
- Refine config.ADDITIONAL_STOPWORDS; also, give room for a custom list;

## Meta/Download tab:

- add wordcloud to tooltip, click on tooltip takes to transcript, click on row heightens row, you see description and wordcloud or so

## Transcript/Episode tab:

- Transcript display: Playback if audio present
- Show hits in scrollbar
- dynamic wordcloud next to transcript
  - => move results list to terms tab

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

- Transcriber Class poll will be a fast method without timeout shenanigans. If in progress, it will return this as a status.

## Structure

Function:

- EpisodeStore:
  - enthält auch Statusinfo, Transcripts, Audio - nicht nur RSS-Klon oder Klon der Ressource
  - hat Methode für Metadaten- und Transkript-Abruf, verarbeitet resultierende Datenstrukturen und setzt sie in Store ein

## Dysfunction

# Bugs

