def test_portal_transparencia_client():
    from src.core.api_client import PortalTransparenciaClient
    client = PortalTransparenciaClient(api_key="TEST")
    assert client.base_url == "https://api.portaldatransparencia.gov.br/api-de-dados"
