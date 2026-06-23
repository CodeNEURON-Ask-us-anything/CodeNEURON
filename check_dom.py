import re

with open('frontend/index.js', 'r', encoding='utf-8') as f:
    js_content = f.read()

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

html_ids = re.findall(r'id=[\'"](.*?)[\'"]', html_content)
all_ids_in_html = set(html_ids)

matches = re.findall(r'getElementById\([\'"](.*?)[\'"]\)', js_content)
missing_ids = []
for m in matches:
    if m not in all_ids_in_html:
        missing_ids.append(m)

print("Missing IDs:", set(missing_ids))

print("Missing IDs:", set(missing_ids))
