import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app.py"
MCP_SEARCH = ROOT / "backend" / "mcp_server" / "blog_server.py"
RENDER = ROOT / "render.yaml"


def _call_keywords(path: Path, function_name: str) -> list[set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[set[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name == function_name:
            matches.append({kw.arg for kw in node.keywords if kw.arg})
    return matches


class ProductionRuntimeWiringTests(unittest.TestCase):
    def test_fastapi_runtime_builds_structured_profile_retriever(self):
        text = APP.read_text(encoding="utf-8")
        self.assertIn("StructuredProfileRetriever.from_path(PROFILE_PATH)", text)
        self.assertIn("STATE.structured_docs = structured_retriever.count", text)

    def test_fastapi_hybrid_retriever_receives_structured_signal(self):
        calls = _call_keywords(APP, "HybridRetriever")
        self.assertTrue(calls, "FastAPI runtime must construct HybridRetriever")
        self.assertTrue(
            any("structured_retriever" in keywords for keywords in calls),
            "At least one FastAPI HybridRetriever must receive structured_retriever",
        )

    def test_mcp_search_runtime_receives_structured_signal(self):
        calls = _call_keywords(MCP_SEARCH, "HybridRetriever")
        self.assertTrue(calls, "MCP search runtime must construct HybridRetriever")
        self.assertTrue(
            any("structured_retriever" in keywords for keywords in calls),
            "MCP HybridRetriever must receive structured_retriever",
        )
        text = MCP_SEARCH.read_text(encoding="utf-8")
        self.assertIn("StructuredProfileRetriever.from_path(PROFILE_PATH)", text)

    def test_health_exposes_retrieval_strategy_and_structured_count(self):
        text = APP.read_text(encoding="utf-8")
        self.assertIn('"structured_docs": STATE.structured_docs', text)
        self.assertIn('"retrieval": "semantic+bm25+structured-rrf"', text)

    def test_product_metadata_endpoint_is_present(self):
        text = APP.read_text(encoding="utf-8")
        self.assertIn('@app.get("/capabilities")', text)
        self.assertIn('"name": "Ask Youssef AI"', text)
        self.assertIn('"languages": ["en", "fr", "ar"]', text)
        self.assertIn('"suggestions": [', text)

    def test_feedback_endpoint_is_fixed_schema_and_aggregate(self):
        text = APP.read_text(encoding="utf-8")
        self.assertIn("from feedback import FEEDBACK", text)
        self.assertIn('@app.post("/feedback")', text)
        self.assertIn("FEEDBACK.record(req.rating, req.reason)", text)
        self.assertIn('snapshot["feedback"] = FEEDBACK.snapshot()', text)
        self.assertNotIn("class FeedbackRequest(BaseModel):\n    question:", text)
        self.assertNotIn("class FeedbackRequest(BaseModel):\n    comment:", text)

    def test_render_production_path_uses_inprocess_transport(self):
        text = RENDER.read_text(encoding="utf-8")
        self.assertIn("- key: MCP_TRANSPORT\n        value: inprocess", text)


if __name__ == "__main__":
    unittest.main()
