import os
import sys
import json
import types
import importlib
import pytest

def _make_dummy_sheets_service():
    class DummyService:
        def __init__(self):
            self._last_rows = []
        def spreadsheets(self):
            return self
        def values(self):
            return self
        def append(self, spreadsheetId=None, range=None, valueInputOption=None, insertDataOption=None, body=None):
            self._last_rows = body.get("values", [])
            return self
        def get(self, spreadsheetId=None):
            return self
        def execute(self):
            return {"updates": {"updatedRows": len(self._last_rows)}}
    return DummyService()

@pytest.fixture
def amazon_agent(monkeypatch):
    fake_sa = {
        "type": "service_account",
        "project_id": "dummy-project",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIID...FAKE\n-----END PRIVATE KEY-----\n",
        "client_email": "test@dummy.iam.gserviceaccount.com"
    }
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(fake_sa))
    monkeypatch.setenv("SPREADSHEET_ID", "sheet_test_123")
    monkeypatch.setenv("SHEET_NAME", "Sheet1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    if "googleapiclient" not in sys.modules:
        ga = types.ModuleType("googleapiclient")
        ga.discovery = types.SimpleNamespace()
        sys.modules["googleapiclient"] = ga
        sys.modules["googleapiclient.discovery"] = ga.discovery
    if "google.oauth2" not in sys.modules:
        go = types.ModuleType("google.oauth2")
        go.service_account = types.SimpleNamespace()
        sys.modules["google.oauth2"] = go
        sys.modules["google.oauth2.service_account"] = go.service_account

    try:
        import googleapiclient.discovery as gad
        monkeypatch.setattr(gad, "build", lambda service, version, credentials=None: _make_dummy_sheets_service(), raising=False)
    except Exception:
        sys.modules["googleapiclient"].discovery.build = lambda service, version, credentials=None: _make_dummy_sheets_service()

    try:
        import google.oauth2.service_account as gas
        monkeypatch.setattr(gas.Credentials, "from_service_account_info", lambda info, scopes=None: object(), raising=False)
    except Exception:
        sys.modules["google.oauth2.service_account"].Credentials = types.SimpleNamespace(from_service_account_info=lambda info, scopes=None: object())

    class DummyApifyClient:
        async def quick_test(self):
            return True
        async def scrape_amazon_products(self, **kwargs):
            return {"success": True, "products": []}

    class DummyMemoryManager:
        async def learn_from_analysis(self, *args, **kwargs):
            return True

    import importlib as _importlib
    try:
        _importlib.import_module("app")
    except Exception:
        pass

    monkeypatch.setattr("app.apify_client", DummyApifyClient(), raising=False)
    monkeypatch.setattr("app.memory_manager", DummyMemoryManager(), raising=False)

    agent_mod = importlib.import_module("app.agent")
    importlib.reload(agent_mod)

    inst = agent_mod.AmazonAgent()
    return inst
