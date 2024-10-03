import re
import sys
import uuid
import json
import typer
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List


app = typer.Typer()


def split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    return re.split(
        r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<![\w\s][A-Z]\.)(?<=\.|\?|\!)\s", text
    )


@app.command()
def to_json(src: Path, tgt: Path) -> None:
    """
    Takes an HTML source file with an expected structure and saves its
    segmented sentences in tgtfile as JSON.
    """
    with open(src, "r") as f:
        soup = BeautifulSoup(f, features="html.parser")

    segments = []

    for c, chapter in enumerate(soup.find_all(name="div", class_="chapter")):
        title = chapter.h2.text
        title = re.sub(r"\n", " ", title)

        paras = chapter.find_all(name="p")

        for p, para in enumerate(paras):
            text = para.text
            text = re.sub(r"\n", " ", text)
            text = re.sub(r"\xa0", " ", text)
            sentences = split_sentences(text)

            for s, sentence in enumerate(sentences):
                sentence = re.sub(r" +", " ", sentence)
                sentence = re.sub(r"^\s+", "", sentence)
                segment = {
                    "id": f"utterance_{str(uuid.uuid4())[:8]}",
                    "text": sentence,
                    "title": title,
                    "chapter": c + 1,
                    "paragraph": p + 1,
                    "sentence": s + 1,
                }
                segments.append(segment)

    with open(tgt, "w") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    app()
