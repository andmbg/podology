from pathlib import Path

from nltk import word_tokenize, pos_tag, ne_chunk, Tree
from nltk.corpus import stopwords
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from wordcloud import WordCloud
import numpy as np
import pandas as pd

from kfsearch.data.models import EpisodeStore
from config import ADDITIONAL_STOPWORDS

stop_words = set(stopwords.words("english"))
stop_words.update(ADDITIONAL_STOPWORDS)


def get_named_entities(text) -> list[tuple[str, str]]:
    """
    Extract named entities from the given text using NLTK's named entity chunker.
    Returns a list of tuples containing the entity name and its type.
    """
    tokens = word_tokenize(text)
    # tokens = [word for word in tokens if word.lower() not in stop_words]
    pos_tags = pos_tag(tokens)

    # Chunk the tokens into named entities:
    chunked = ne_chunk(pos_tags)

    named_entities = []

    for subtree in chunked:
        if isinstance(subtree, Tree):  # Named Entity subtree
            entity_name = " ".join(token for token, pos in subtree.leaves())
            entity_type = subtree.label()

            if entity_name.lower() not in stop_words:
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
        width=800, height=400, background_color="white"
    ).generate_from_frequencies(namedict)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout()

    return fig


def type_proximity(type_token_dict: dict) -> pd.DataFrame:
    """
    Calculate the proximity score between different tokens based on their indices.
    The proximity score is defined as the sum of the exponential of the negative squared differences
    between the indices of the tokens.

    :param type_token_dict: A dictionary where keys are types and values are lists of indices.
        Currently, index means order of a named entity in a list of NE extracted from the transcript.
        That list's quality is not guaranteed, maybe we need more work here.
    :return: A DataFrame containing the half matrix of proximity scores between between types in a
        transcript.
    """

    def proximity_score(arr_i, arr_j):
        """
        Here, we're free to use any other function that expresses
        distance between types and their tokens in an episode. It
        might even be something parametric, so we could fit it to
        our expectations.
        """
        # Start out with the plain distance in tokens or named entities:
        diff = np.abs(arr_i[:, None] - arr_j).astype(float)

        # Here is where we put the mapping function from each distance to a score:
        tokenscore = 1 / diff**2

        # Sum up for this type pair:
        typescore = np.sum(tokenscore)

        # Use log values, as we deal with many orders of magnitude:
        typescore = np.log(typescore)

        return typescore

    keys = list(type_token_dict.keys())
    values = [np.array(type_token_dict[key]) for key in keys]
    matrix = np.zeros((len(keys), len(keys)))

    for i, arr_i in enumerate(values):
        # Only calculate upper triangle of matrix:
        for j in range(i + 1, len(values)):
            proxscore = proximity_score(arr_i, values[j])
            matrix[i, j] = proxscore

    # From matrix to tidy df form:
    matrix_df = pd.DataFrame(matrix, index=keys, columns=keys)
    upper_triangle = matrix_df.where(
        np.triu(np.ones(matrix_df.shape), k=1).astype(bool)
    )

    prox_df = upper_triangle.stack().reset_index()
    prox_df.columns = ["type", "other_type", "proximity"]

    return prox_df
