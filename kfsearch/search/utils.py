import re
from bs4 import BeautifulSoup
from dash import html


def extract_text_from_html(html_string):
    """
    Parse strings such as the description of a podcast episode, which can contain HTML
    tags, and convert them to Dash components.
    """
    soup = BeautifulSoup(html_string, 'html.parser')
    return soup.get_text()


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


def format_time(seconds: float) -> str:
    """
    Convert seconds into HH:MM:SS format.
    Example: 3665.5 -> "01:01:05"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def make_index_name(project_name):
    """
    Fixes an Elasticsearch index name based on the following rules:
    - Must be lowercase
    - Cannot include spaces
    - Cannot start with an underscore
    - Cannot contain commas, asterisks, or backslashes
    - Cannot be longer than 255 bytes
    """
    # Convert to lowercase
    project_name = project_name.lower()

    # Replace spaces with underscores
    project_name = project_name.replace(' ', '_')

    # Remove leading underscores
    project_name = re.sub(r'^_+', '', project_name)

    # Remove invalid characters
    project_name = re.sub(r'[,*\\]', '', project_name)

    # Truncate to 255 bytes
    project_name = project_name.encode('utf-8')[:255].decode('utf-8', 'ignore')

    return project_name


def highlight_search_term(text, search_term):
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
    highlighted_text = pattern.sub(lambda m: f"<bling>{m.group()}</bling>", text)

    return highlighted_text
