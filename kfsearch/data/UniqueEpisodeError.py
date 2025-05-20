# pylint: disable=W1514




class UniqueEpisodeError(Exception):
    """
    Raised when trying to add an episode to the store that already exists.
    """