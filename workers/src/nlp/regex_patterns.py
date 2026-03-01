import re

# Strict Regex Patterns for Political Data Extraction
CNPJ_PATTERN = r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"
CPF_PATTERN = r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"
CURRENCY_PATTERN = r"R\$\s?(\d{1,3}(\.\d{3})*|\d+)(,\d{2})?"

# Keyword triggers for focus area extraction
KEYWORDS_SUSPICIOUS = [
    "dispensa de licitação",
    "inexigibilidade",
    "contratação direta",
    "sem licitação",
    "emergencial"
]

def find_patterns(text: str):
    return {
        "cnpjs": list(set(re.findall(CNPJ_PATTERN, text))),
        "cpfs": list(set(re.findall(CPF_PATTERN, text))),
        "valores": list(set(re.findall(CURRENCY_PATTERN, text)))
    }

def get_context_window(text: str, keyword: str, window: int = 300):
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return None
    start = max(0, idx - window // 2)
    end = min(len(text), idx + window // 2)
    return text[start:end]
