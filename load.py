from kfsearch.data.models import EpisodeStore
from config import PROJECT_NAME, CONNECTOR, TRANSCRIBER, LANGUAGE


store = EpisodeStore(name=PROJECT_NAME)

store.set_connector(CONNECTOR)
store.set_transcriber(TRANSCRIBER)
store.populate()

store.to_json()
