import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "app.py"


class VercelEntrypointContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ENTRYPOINT.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_fast_stream_wrapper_matches_backend_stream_signature(self):
        funcs = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        fn = funcs.get("_stream_with_fast_public_routes")
        self.assertIsNotNone(fn)
        self.assertIsInstance(fn, ast.FunctionDef)
        self.assertEqual([arg.arg for arg in fn.args.args], ["question", "history"])
        self.assertEqual(len(fn.args.defaults), 1)

    def test_entrypoint_uses_current_router_contract(self):
        self.assertIn("_backend.route_question(question)", self.source)
        self.assertNotIn("_backend.route_intent", self.source)
        self.assertNotIn("_backend._normalize_text", self.source)

    def test_backend_stream_is_delegated_as_sync_generator(self):
        self.assertIn("yield from _original_stream(question, history)", self.source)
        self.assertNotIn("async for event in _original_stream", self.source)

    def test_fast_routes_emit_backend_sse_schema(self):
        self.assertIn('_backend._sse("final", answer=answer, tools_used=[])', self.source)
        self.assertNotIn("event: {event}", self.source)


if __name__ == "__main__":
    unittest.main()
