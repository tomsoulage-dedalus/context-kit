import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "context-check" / "scripts"))

import check_context  # noqa: E402


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class CheckContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "config", "user.email", "test@example.com")
        sh(self.repo, "git", "config", "user.name", "test")
        self.write("src/orders/order.service.ts", "export class OrderService { cancelOrder() {} }\n")
        self.write("src/orders/order.model.ts", "export interface OrderApi { id: number }\n")
        self.write("src/billing/invoice.ts", "import { OrderService } from '@shop/orders';\n")
        self.commit("init")
        self.sha = sh(self.repo, "git", "rev-parse", "--short", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, content):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))

    def commit(self, message):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "-m", message)

    def context(self, body, provenance=True):
        head = f"Verified at commit {self.sha} on 2026-01-01.\n" if provenance else ""
        self.write("src/orders/CONTEXT.md", f"# Context: src/orders\n\n{head}{body}")
        self.write("ARCHITECTURE.md", "| `src/orders` | [CONTEXT.md](src/orders/CONTEXT.md) |\n")

    def run_check(self, *extra):
        args = check_context.argparse.Namespace(
            path=[], root=str(self.repo), changed_since=None, max_lines=80, stale_after=1,
            strict=False, format="text")
        for key, value in extra:
            setattr(args, key, value)
        return [(f.level, f.message) for f in check_context.run(args)]

    def test_valid_context_has_no_findings(self):
        self.context("Import: `@shop/orders`\n\n- `OrderService.cancelOrder()` in `order.service.ts`,"
                     " model `OrderApi[]`, see `src/billing/`. `'NONE'` and `a -> b` are ignored.\n")
        self.assertEqual(self.run_check(), [])

    def test_detects_missing_symbol_path_alias_and_link(self):
        self.context("`RefundService`, `refund.service.ts`, `@shop/refunds`, [x](../nowhere.md)\n")
        messages = [m for level, m in self.run_check() if level == "error"]
        self.assertEqual(len(messages), 4, messages)

    def test_symbol_only_mentioned_in_markdown_is_missing(self):
        self.write("docs/notes.md", "GhostService\n")
        self.context("`GhostService`\n")
        self.assertIn(("error", "symbol not found in code: `GhostService`"), self.run_check())

    def test_fenced_blocks_are_ignored(self):
        self.context("```\n`GhostService`\n```\n")
        self.assertEqual(self.run_check(), [])

    def test_missing_provenance_and_orphan(self):
        self.context("Nothing.\n", provenance=False)
        os.remove(self.repo / "ARCHITECTURE.md")
        messages = [m for _, m in self.run_check()]
        self.assertTrue(any("missing provenance" in m for m in messages))
        self.assertTrue(any("not linked" in m for m in messages))

    def test_stale_module_and_changed_since(self):
        self.context("`OrderService`\n")
        self.commit("docs")
        self.write("src/orders/order.service.ts", "export class OrderService { cancelOrder() {} refund() {} }\n")
        self.commit("feature")
        messages = [m for _, m in self.run_check(("changed_since", "HEAD~1"))]
        self.assertTrue(any("touched the module since the card" in m for m in messages), messages)
        self.assertTrue(any("CONTEXT.md did not" in m for m in messages), messages)

    def test_urls_routes_and_mime_types_are_ignored(self):
        self.context("`http://localhost:4200`, `/api/orders`, `application/json`, `text/html`\n")
        self.assertEqual(self.run_check(), [])

    def test_code_and_card_changed_in_same_commit_is_fresh(self):
        self.context("`OrderService`\n")
        self.commit("docs")
        self.write("src/orders/order.service.ts", "export class OrderService { cancelOrder() {} refund() {} }\n")
        self.write("src/orders/CONTEXT.md", (self.repo / "src/orders/CONTEXT.md").read_text() + "- refund\n")
        self.commit("feature with card update")
        self.assertEqual(self.run_check(), [])

    def test_changed_since_uses_merge_base(self):
        self.context("`OrderService`\n")
        self.commit("docs")
        sh(self.repo, "git", "checkout", "-q", "-b", "feature")
        sh(self.repo, "git", "checkout", "-q", "main")
        self.write("src/orders/order.service.ts", "export class OrderService { cancelOrder() {} other() {} }\n")
        self.write("src/orders/CONTEXT.md", (self.repo / "src/orders/CONTEXT.md").read_text() + "- other\n")
        self.commit("main moves")
        sh(self.repo, "git", "checkout", "-q", "feature")
        messages = [m for _, m in self.run_check(("changed_since", "main"))]
        self.assertFalse(any("CONTEXT.md did not" in m for m in messages), messages)

    def test_line_budget(self):
        self.context("line\n" * 100)
        self.assertTrue(any("budget" in m for _, m in self.run_check()))


if __name__ == "__main__":
    unittest.main()
