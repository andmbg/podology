# Features to do

- Die Indizierung geht momentan nur vollständig. Man kann nicht einem laufenden System neue Episoden zufügen, die dan kumulativ indiziert werden. Wahrscheinlich in setup_es.py pro Episode testen, ob sie schon im Index ist und nur bei False indizieren.
- Elasticsearch indexing presumes a specific date format that not all podcasts may adhere to. We may have to implement a custom date parser or unify the date format across all podcasts.
- Lemonfox speaker assignment is imprecise around turn ends. We may have to, instead of taking over Lemonfox's 
  speaker assignment, use the word-level assignments and assign the speaker to the whole turn ourselves.
- 