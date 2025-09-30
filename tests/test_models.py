import pytest
from ..podology.data.EpisodeStore import EpisodeStore
from ..podology.data.Episode import Episode


@pytest.fixture
def episode_store():
    return EpisodeStore()


@pytest.fixture
def episode():
    url = (
        "https://static1.squarespace.com/static/58bc3c86b8a79bbdc67b182c/"
        "t/5ac11e050e2e721df0298e13/1522605573406/Wonk.mp3/original/Wonk.mp3"
    )
    return Episode(audio_url=url)


def test_episode_repr(episode_store, episode):
    episode_store.add(episode)
    expected_repr = (
        "Episode (id 'Wonk')\n"
        "  Store: episode_store\n"
        "  Title: ---\n"
        "  Audio: ---\n"
        "  TrScr: ---\n"
        "  URL:   https://static1.squarespace.com/static/58bc3c86b8a79bbdc67b182c/"
        "t/5ac11e050e2e721df0298e13/1522605573406/Wonk.mp3/original/Wonk.mp3\n"
    )
    assert (
        repr(episode) == expected_repr
    ), f"Expected: {expected_repr}, but got: {repr(episode)}"
