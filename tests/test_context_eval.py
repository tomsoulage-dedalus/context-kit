import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "context-eval" / "scripts" / "context_eval.py"

FAKE_AGENT = textwrap.dedent("""
    import pathlib, sys
    repo = pathlib.Path(sys.argv[1])
    target = "src/orders/order.service.ts" if (repo / "src/orders/CONTEXT.md").exists() else "src/misc.ts"
    path = repo / target
    path.write_text(path.read_text() + "export function cancelOrder() {}\\n" if path.exists() else "let x: any;\\n")
    if sys.argv[2:] == ['{"commit": true}']:
        import subprocess
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=a", "-c", "user.email=a@b", "commit", "-qm", "agent"],
                       check=True)
""")


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class ContextEvalTest(unittest.TestCase):
    def test_run_compares_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src/orders").mkdir(parents=True)
            sh(repo, "git", "init", "-q", "-b", "main")
            sh(repo, "git", "config", "user.email", "t@example.com")
            sh(repo, "git", "config", "user.name", "t")
            (repo / "src/orders/order.service.ts").write_text("export class OrderService {}\n")
            sh(repo, "git", "add", "-A")
            sh(repo, "git", "commit", "-q", "-m", "base")
            base = sh(repo, "git", "rev-parse", "HEAD")
            (repo / "src/orders/CONTEXT.md").write_text("# Context\n")
            agent = Path(tmp) / "agent.py"
            agent.write_text(FAKE_AGENT)
            evals = repo / "context-evals"
            (evals / "tasks").mkdir(parents=True)
            (evals / "config.json").write_text(json.dumps({
                "agent_command": f"{sys.executable} {agent} {{repo}} '{{\"commit\": true}}'",
                "variants": {"no-context": {"context_source": "none"},
                             "context": {"context_source": "working-tree"}},
            }))
            (evals / "tasks/t.json").write_text(json.dumps({"tasks": [{
                "id": "cancel", "base_ref": base, "prompt": "Add cancelOrder",
                "required_changed_paths": ["src/orders/order.service.ts"], "max_changed_files": 2,
                "required_patterns": [{"name": "cancel", "glob": "src/**", "pattern": r"cancelOrder\("}],
                "forbidden_patterns": [{"name": "no any", "glob": "src/**", "pattern": r":\s*any\b"}],
                "commands": [{"name": "true", "argv": ["true"]}],
            }]}))
            out = subprocess.run([sys.executable, str(SCRIPT), "run", "-n", "1"], cwd=repo,
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
            results = list((repo / "context-evals/results").glob("*.jsonl"))
            records = {r["variant"]: r for r in map(json.loads, results[0].read_text().splitlines())}
            self.assertTrue(records["context"]["success"])
            self.assertEqual(records["context"]["localization_recall"], 1.0)
            self.assertEqual(records["context"]["context_files"], ["src/orders/CONTEXT.md"])
            self.assertFalse(records["no-context"]["success"])
            self.assertEqual(records["no-context"]["changed_files"], ["src/misc.ts"])
            self.assertIn("| cancel | context | 1 | 1/1 |", out.stdout)
            self.assertEqual(sh(repo, "git", "worktree", "list").count("\n"), 0)


if __name__ == "__main__":
    unittest.main()
