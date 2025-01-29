import re


def find_nested_dict_by_key_value(data, target_key, target_value):
    """
    Dash Bootstrap elements are large and convoluted. To get to a text in a card, you
    go through numerous nested dictionaries. This function helps to find a card in our
    search results with a specific ID.

    :param data: A dictionary or list of dictionaries.
    :param str target_key: The key to search for.
    :param str target_value: The value to search for.
    """
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


def get_para(triggered_id, search_results, ctx):
    """
    Extract from a clicked result card the chapter and paragraph. Retrieve the whole paragraph text.
    """
    # Get clicked card:
    res = find_nested_dict_by_key_value(search_results, "id", triggered_id)
    res = res["children"]["props"]["children"]["props"]["children"][0]["props"][
        "children"
    ][1]["props"]["children"]["props"]["children"]

    ch, para, sent = (int(re.findall(r"\d+$", i)[0]) for i in res.split(", "))
    para = [s["text"] for s in book if s["chapter"] == ch and s["paragraph"] == para]

    restext = "".join(para)

    return restext
