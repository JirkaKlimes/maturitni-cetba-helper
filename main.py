import json
from rich import print
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import requests
import toml


def perform_ddg_search(name, config):
    HEADERS = config['headers']
    SOURCE_URL = config['sources']['url']
    MAX_SOURCES = config['sources']['max_n']

    with DDGS(headers=HEADERS) as ddgs:
        query = f'site:{SOURCE_URL} {name}'
        results = {
            r['href']: r['title']
            for r in ddgs.text(query, max_results=MAX_SOURCES)
        }

    return results


def display_search_results(results):
    print(f'Nalezeno potencialnich zdroju: {len(results)}')
    for i, title in enumerate(results.values()):
        print(f'({i}) {title}')


def select_sources(results):
    options = ' '.join(map(str, range(len(results))))
    print(f"Select sources (default: '{options}') ", end='')
    source_indices = input()

    if source_indices:
        source_indices = list(
            map(
                lambda s: int(s.strip()),
                source_indices.replace(',', ' ').split()
            )
        )
        sources = [list(results.keys())[s] for s in source_indices]
    else:
        sources = list(results.keys())

    return sources


def scrape_source(url, HEADERS):
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    article = soup.find('div', {'class': 'inside-article'})
    tags = article.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    texts = [tag.get_text() for tag in tags]
    text = " ".join(texts)
    return text


def read_sources(sources, HEADERS):
    scraped_sources = []
    print("Cteni zdroju...")
    for source in sources:
        print(source)
        scraped_sources.append(scrape_source(source, HEADERS))
    return scraped_sources


def prepare_messages(scraped_sources, template):
    messages = [
        {
            'role': 'system',
            'content': (
                "You will be given few sources of text about some literary work"
                "along with template full of placeholders,"
                "your job is to return raw .md text"
                "that can be directly saved to .md file without any post processing."
                "do NOT add '```md', just return raw markdown text"
                "You can change the template a bit, just overall it should have similar structure"
            )
        },
        {
            'role': 'system',
            'content': f"Sources: {' '.join(scraped_sources)}"
        },
        {
            'role': 'system',
            'content': f"Template: {template}"
        }
    ]
    return messages


def create_tools(tool_name):
    tools = [
        {
            "type": "function",
            "function": {
                    "name": tool_name,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "filename in format `{autor}_{dilo}.md`",
                            },
                            "content": {
                                "type": "string",
                                "description": "rozbor dila k maturite",
                            },
                        },
                        "required": ["filename", "content"],
                    },
            },
        }
    ]
    return tools


def make_openai_request(messages, tools, tool_name, api_key):
    response = requests.post(
        url='https://api.openai.com/v1/chat/completions',
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        data=json.dumps({
            "model": 'gpt-3.5-turbo-0613',
            "temperature": 0.3,
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": tool_name}}
        })
    )
    print(response.json())
    return response


if __name__ == "__main__":
    config = toml.load('./config.toml')

    print("Zadejte nazev dila: ", end='')
    name = input()

    results = perform_ddg_search(name, config)
    display_search_results(results)

    sources = select_sources(results)
    sources_scraped = read_sources(sources, config['headers'])

    with open('./template.md') as f:
        template = f.read()

    messages = prepare_messages(sources_scraped, template)

    tool_name = "rozbor_dila"
    tools = create_tools(tool_name)

    response = make_openai_request(
        messages, tools, tool_name, config['openai']['api_key']
    )

    data = response.json()
    args = json.loads(data['choices'][0]['message']
                      ['tool_calls'][0]['function']['arguments'])

    filename, content = args.values()

    with open(filename, 'w') as f:
        f.write(content)
