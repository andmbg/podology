"""NLP-related computations"""

from typing import List

from nltk import word_tokenize, pos_tag, ne_chunk, Tree
from nltk.corpus import stopwords
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
import pandas as pd

from kfsearch.data.models import Episode, DiarizedTranscript
from config import ADDITIONAL_STOPWORDS

stop_words = set(stopwords.words("english"))
stop_words.update(ADDITIONAL_STOPWORDS)


def get_named_entities(text) -> list[tuple[str, str]]:
    """
    Extract named entities from the given text using NLTK's named entity chunker.
    Returns a list of tuples containing the entity name and its type.

    :param text: The whole contiguous input text from which to extract named entities.
    :return: A list of tuples, where each tuple contains the entity name and its type.
    """
    tokens = word_tokenize(text)
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


def get_named_entity_tokens(episode: Episode) -> List[str]:
    """
    For a given episode, store in the stats database the tokens of named
    entities and their index among NEs. This facilitates type frequency and
    proximity calculations.
    """
    # Get the transcript text:
    transcript = DiarizedTranscript(episode)
    text = [i["text"] for i in transcript.to_json()]
    text = " ".join(text)

    # Get the named entities:
    named_entities: List[str] = [i[0] for i in get_named_entities(text)]

    return named_entities


def get_wordcloud(episode: Episode) -> plt.Figure:
    """
    Create a word cloud Figure for the given episode.

    :param episode: The episode object for which to create the word cloud.
    :return: A matplotlib Figure object containing the word cloud.
    """
    # Plain text of transcript without speaker labels:
    diarized_transcript = DiarizedTranscript(episode)
    text = [i["text"] for i in diarized_transcript.to_json()]
    text = " ".join(text)

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
    Type proximity score: Expresses how closely related two dictionary entries are in a given transcript.
      For each token of TYPE_A, if >0 tokens of TYPE_B are within a maximum perimeter, we take the squared
      distances in words and do 1/x with each. Then, the sum of these scores is the proximity SCORE(A, B).

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
