from src.loaders.rfb_cnpj_loader import parse_qsa_line, ingest_qsa_to_neo4j
from unittest.mock import MagicMock

def test_parse_qsa_line():
    # Simulating a stripped line from Receita Federal CSV
    line = "12345678;1;2;Nome do Socio;..." 
    parsed = parse_qsa_line(line)
    assert parsed["cnpj_basico"] == "12345678"
    assert parsed["nome_socio"] == "Nome do Socio"

def test_ingest_qsa_to_neo4j():
    mock_session = MagicMock()
    data = [{"cnpj_basico": "12", "nome_socio": "Manoel"}]
    ingest_qsa_to_neo4j(mock_session, data)
    assert mock_session.run.called
