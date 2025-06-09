"""NLP-related computations"""

from typing import List
import multiprocessing

import matplotlib
from nltk import word_tokenize, pos_tag, ne_chunk, Tree
from nltk.corpus import stopwords
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
import pandas as pd

from kfsearch.data.Episode import Episode
from kfsearch.data.Transcript import Transcript
from config import ADDITIONAL_STOPWORDS

stop_words = set(stopwords.words("english"))
stop_words.update(ADDITIONAL_STOPWORDS)


def named_entities_whole_text(text) -> list[tuple[str, str]]:
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


def get_wordcloud(episode: Episode) -> plt.Figure:
    """
    Create a word cloud Figure for the given episode.

    :param episode: The episode object for which to create the word cloud.
    :return: A matplotlib Figure object containing the word cloud.
    """
    # Plain text of transcript without speaker labels:
    transcript = Transcript(episode)
    text = " ".join([i["text"] for i in transcript.segments()])
    names = named_entities_whole_text(text)
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

    :param type_token_dict: A dictionary where keys are types and values are a lists of timestamps.
    :return: A DataFrame containing the half matrix of proximity scores between between types in a
        transcript.
    """

    def proximity_score(arr_i, arr_j):
        """
        Given two arrays of timestamps, calculate the proximity score
        between them. The score is calculated as follows:
        1. Calculate the absolute differences between each pair of timestamps.
        2. For each difference, calculate the inverse square (1/difference^2).
        3. Sum these values to get a score for the type pair.
        4. Use the logarithm of the score to handle large ranges.
        """
        # Start out with the plain distance in tokens or named entities:
        diff = np.abs(arr_i[:, None] - arr_j).astype(float)

        # Here is where we put the mapping function from each distance to a score:
        tokenscore = 1 / (diff**2 + 1e-6)  # Add a small constant to avoid division by zero

        # Sum up for this type pair:
        typescore = np.sum(tokenscore)

        # Use log values, as we deal with many orders of magnitude:
        typescore = np.log(typescore)

        return typescore

    keys = list(type_token_dict.keys())  # list of type names
    values = [np.array(type_token_dict[key]) for key in keys]  # list of arrays of timestamps
    matrix = np.zeros((len(keys), len(keys)))

    for i, arr_i in enumerate(values):  # arr_i is an array of timestamps for type i
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


def timed_named_entity_tokens(transcript: Transcript) -> List:
    """
    Extract named entities from the given transcript and associate them with timestamps.
    
    :param transcript: A list of dictionaries, where each dictionary contains "text", "start", and "end".
    :return: A list of tuples (entity_name, entity_type, word_index).
    """
    argslist = []
    for segment in transcript.segments(transcript_metadata=["text", "start", "end"]):
        timestamp = round((segment["start"] + segment["end"]) / 2, 2)
        argslist.append((segment["text"], timestamp))

    with multiprocessing.Pool(processes=multiprocessing.cpu_count() - 2) as pool:
        results = pool.map(process_segment_wrapper, argslist)

    flat_results = [item for sublist in results for item in sublist]

    return flat_results




def process_segment_wrapper(argslist):
    """
    Wrapper function to unpack arguments for multiprocessing.
    """
    return process_segment_with_word_index(*argslist)


def process_segment_with_word_index(segment, start_time):
    """
    Process a single segment to extract named entities and associate them with word indices.
    
    :param segment: A dictionary containing "text", "start", and "end".
    :param start_index: The starting word index for this segment.
    :return: A list of tuples (entity_name, entity_type, word_index).
    """
    # Tokenize the segment text
    tokens = word_tokenize(segment)
    pos_tags = pos_tag(tokens)
    chunked = ne_chunk(pos_tags)

    named_entities = []

    for subtree in chunked:
        if isinstance(subtree, Tree):  # Named Entity subtree
            entity_name = " ".join(token for token, pos in subtree.leaves())
            if entity_name.lower() not in stop_words:
                named_entities.append((entity_name, start_time))
        
    return named_entities
