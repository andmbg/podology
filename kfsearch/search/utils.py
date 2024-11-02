import re
import json
from dash import html

book = json.load(open("data/interim/poe.json", "r"))


def find_nested_dict_by_key_value(data, target_key, target_value):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key and value == target_value:
                return data
            result = find_nested_dict_by_key_value(value, target_key, target_value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_nested_dict_by_key_value(item, target_key, target_value)
            if result is not None:
                return result
    return None


def process_highlighted_text(text):
    parts = re.split(r"(<bling>.*?</bling>)", text)
    result = []

    for part in parts:
        if part.startswith("<bling>") and part.endswith("</bling>"):
            highlighted = part[7:-8]  # Remove <bling> and </bling>
            result.append(html.Mark(highlighted))
        else:
            result.append(html.Span(part))

    return html.Div(result)


def get_para(triggered_id, search_results, ctx):
    """
    Extract from a clicked result card the chapter and paragraph. Retrieve the whole paragraph text.
    """
    res = find_nested_dict_by_key_value(search_results, 'id', triggered_id)
    res = res['children']['props']['children']['props']['children'][0]['props']['children'][1]['props']['children']['props']['children']

    ch, para, sent = (int(re.findall(r"\d+$", i)[0]) for i in res.split(', '))
    para = [s["text"] for s in book if s["chapter"] == ch and s["paragraph"] == para]
    
    restext = "".join(para)

    return restext
