from pathlib import Path
from nltk import word_tokenize, pos_tag, ne_chunk, Tree
from nltk.corpus import stopwords
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from wordcloud import WordCloud

from kfsearch.data.models import EpisodeStore
from config import ADDITIONAL_STOPWORDS

stop_words = set(stopwords.words("english"))
stop_words.update(ADDITIONAL_STOPWORDS)
    

def get_named_entities(text) -> list[tuple[str, str]]:
    tokens = word_tokenize(text)
    tokens = [word for word in tokens if word.lower() not in stop_words]
    pos_tags = pos_tag(tokens)
    chunked = ne_chunk(pos_tags)

    named_entities = []

    for subtree in chunked:
        if isinstance(subtree, Tree):  # Named Entity subtree
            entity_name = " ".join(token for token, pos in subtree.leaves())
            entity_type = subtree.label()
            named_entities.append((entity_name, entity_type))

    return named_entities


def get_wordcloud(text: str) -> Figure:
    """
    Generate a wordcloud from the named entities in the given text.
    Return it as a matplotlib figure.
    """
    names = get_named_entities(text)
    names = [i[0] for i in names]

    # Get word counts:
    namedict = {}
    for i in names:
        namedict[i] = namedict.get(i, 0) + 1
    
    # Make the cloud:
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color="white"
    ).generate_from_frequencies(namedict)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout()

    return fig
