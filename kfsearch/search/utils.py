import re
from dash import html

def process_highlighted_text(text):
    parts = re.split(r'(<bling>.*?</bling>)', text)
    result = []
    
    for part in parts:
        if part.startswith('<bling>') and part.endswith('</bling>'):
            highlighted = part[7:-8]  # Remove <bling> and </bling>
            result.append(html.Mark(highlighted))
        else:
            result.append(html.Span(part))
    
    return html.Div(result)