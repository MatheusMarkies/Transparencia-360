from unittest.mock import patch
from src.gatherers.transparencia_gatherer import fetch_servidor_remuneracao

@patch('src.core.api_client.PortalTransparenciaClient.get')
def test_fetch_servidor_remuneracao(mock_get):
    mock_get.return_value = [{"remuneracaoBasica": 15000}]
    res = fetch_servidor_remuneracao("12345678900", "202501")
    assert res[0]["remuneracaoBasica"] == 15000
