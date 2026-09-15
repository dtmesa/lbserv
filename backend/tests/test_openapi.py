import json
from pathlib import Path

from app.scripts.export_openapi import render

CONTRACT = Path(__file__).resolve().parents[2] / "openapi" / "openapi.json"


def test_openapi_contract_is_up_to_date() -> None:
    assert CONTRACT.exists(), "Run `make openapi` to export the contract"
    assert json.loads(CONTRACT.read_text()) == json.loads(render()), (
        "openapi/openapi.json is stale. Run `make openapi && make gen`."
    )


def test_errors_documented_as_problem_details() -> None:
    doc = json.loads(render())
    assert "HTTPValidationError" not in doc["components"]["schemas"]
    for path, item in doc["paths"].items():
        for method, op in item.items():
            for status, response in op["responses"].items():
                if status.startswith(("4", "5")):
                    assert list(response["content"]) == ["application/problem+json"], (
                        f"{method.upper()} {path} {status}"
                    )
    events = doc["paths"]["/api/v1/games/{game_id}/events"]["get"]["responses"]["200"]
    assert list(events["content"]) == ["text/event-stream"]
