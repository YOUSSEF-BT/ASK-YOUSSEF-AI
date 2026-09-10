import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIDGET = ROOT / "web" / "widget.js"


class WidgetContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WIDGET.read_text(encoding="utf-8")

    def test_uses_portfolio_brand_color(self):
        self.assertIn('|| "#20b2a6"', self.text)
        self.assertIn("--bg: #0f1418", self.text)
        self.assertIn("--card: #141a1f", self.text)

    def test_uses_public_product_metadata(self):
        self.assertIn('fetch(API + "/capabilities")', self.text)
        self.assertIn("capabilities.suggestions", self.text)

    def test_supports_feedback_without_free_text(self):
        self.assertIn('fetch(API + "/feedback"', self.text)
        self.assertIn('JSON.stringify({ rating: rating, reason: reason })', self.text)
        self.assertNotIn("feedbackComment", self.text)

    def test_supports_conversation_reset_and_bounded_history(self):
        self.assertIn("function resetChat()", self.text)
        self.assertIn("history = []", self.text)
        self.assertIn("history.length > 16", self.text)

    def test_supports_three_interface_languages(self):
        self.assertIn('lang.indexOf("ar")', self.text)
        self.assertIn('lang.indexOf("fr")', self.text)
        self.assertIn("EN · FR · AR", self.text)

    def test_widget_does_not_embed_provider_secret(self):
        forbidden = ["GEMINI_API_KEY=", "OPENAI_API_KEY=", "sk-proj-", "AIzaSy"]
        for marker in forbidden:
            self.assertNotIn(marker, self.text)

    def test_template_and_css_initialize_before_mount(self):
        self.assertLess(self.text.index("var TEMPLATE ="), self.text.rindex("askYoussefWidget();"))
        self.assertLess(self.text.index("var CSS ="), self.text.rindex("askYoussefWidget();"))


if __name__ == "__main__":
    unittest.main()
