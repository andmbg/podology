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

### Animated Word Cloud

Battle plan:

- re-do indexed_named_entities() to named_entity_tokens():
  instead of word index, we want the middle between start and end time of the segment where the NE appears
  Check **outcome**: list of NE tokens with float timestamp
- Word layout:
  Based on above, add word_layout(), which for each type of the episode, computes an xy position on the canvas based on inverse time proximity
  Check **outcome**: make a test plot with plotly or so; make sure words are spaced evenly, not all jammed to the margins
  If suboptimal: try different optimization params
- Word prominence - 2 possible ways:
  1. The bitmap way:
     Make a time grid for the episode, place tokens on it, compute prominence per timestep (by some function like linear, or dampened)
     Send to Blender the layout and prominence grid
     **Outcome**: e.g. dataframe; could plot as linegraph in plotly
  2. The vector way:
     For each type, note the timestamp and say, this word gets presence with function (linear/dampened) centered around this timestamp.
     In Blender, figure out how overlapping presence functions per word translate to one presence function
     (could probably do a "take the highest of all triangles of this word at this frame")
     **Outcome**: in fact no more than a timestamp-token dict with info on what presence function is used (even that could be set in Blender)
- Animate. Basic idea:
  - types get a size based on frequency (dampened! like log)
  - words are placed on canvas (solve the word size-canvas dimensions problem!)
  - each word's visual properties are modulated by the prominence data:
  - ideas for mapping:
    1. prominence ~ opacity
    2. max prominence is z-location (the canvas); everything below is higher z-distance to camera, can involve blur (depth of field effect)

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

