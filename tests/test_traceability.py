import os
import csv
import unittest

class TestProjectSukoonTraceability(unittest.TestCase):
    def setUp(self):
        self.workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def test_traceability_matrix_exists_and_valid(self):
        csv_path = os.path.join(self.workspace, "REQUIREMENT_TRACEABILITY.csv")
        self.assertTrue(os.path.exists(csv_path), f"Traceability matrix missing at {csv_path}")
        
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {
                "requirement_id", 
                "requirement", 
                "source_document", 
                "implementation_owner", 
                "implementation_file", 
                "test_id", 
                "status", 
                "evidence"
            }
            self.assertTrue(required_cols.issubset(set(reader.fieldnames or [])), "CSV missing required headers")
            
            rows = list(reader)
            self.assertGreaterEqual(len(rows), 40, f"Expected at least 40 requirements, found {len(rows)}")
            
            # Verify key requirement categories exist
            prefixes = {r["requirement_id"].split("-")[1] for r in rows}
            self.assertIn("ARCH", prefixes)
            self.assertIn("RISK", prefixes)
            self.assertIn("LIVE", prefixes)
            self.assertIn("DATA", prefixes)
            self.assertIn("ORD", prefixes)
            self.assertIn("RES", prefixes)
            self.assertIn("SAIG", prefixes)
            self.assertIn("EVO", prefixes)
            self.assertIn("DEP", prefixes)
            self.assertIn("SEC", prefixes)

    def test_governance_and_decision_documents(self):
        adrs = os.path.join(self.workspace, "ARCHITECTURE_DECISIONS.md")
        self.assertTrue(os.path.exists(adrs), "ARCHITECTURE_DECISIONS.md missing")
        with open(adrs, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ADR-001", content)
            self.assertIn("ADR-002", content)
            self.assertIn("Sukoon Guardian", content)
            self.assertIn("llama.cpp", content)
            
        oq = os.path.join(self.workspace, "OPEN_QUESTIONS.md")
        self.assertTrue(os.path.exists(oq), "OPEN_QUESTIONS.md missing")
        with open(oq, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("LRS", content)
            self.assertIn("IEX", content)
            
        dep = os.path.join(self.workspace, "DEPENDENCY_REGISTRY.md")
        self.assertTrue(os.path.exists(dep), "DEPENDENCY_REGISTRY.md missing")
        with open(dep, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("APPROVED", content)
            self.assertIn("fastapi", content.lower())
            self.assertIn("pydantic", content.lower())

    def test_project_structure_separation(self):
        backend = os.path.join(self.workspace, "project-sukoon-backend")
        dashboard = os.path.join(self.workspace, "project-sukoon-dashboard")
        spec = os.path.join(self.workspace, "specification")
        
        self.assertTrue(os.path.isdir(backend), "project-sukoon-backend directory missing")
        self.assertTrue(os.path.isdir(dashboard), "project-sukoon-dashboard directory missing")
        self.assertTrue(os.path.isdir(spec), "specification directory missing")
        
        # Check backend key modules
        self.assertTrue(os.path.exists(os.path.join(backend, "pyproject.toml")))
        self.assertTrue(os.path.exists(os.path.join(backend, "requirements.txt")))
        self.assertTrue(os.path.exists(os.path.join(backend, ".env.example")))
        self.assertTrue(os.path.exists(os.path.join(backend, "Dockerfile")))
        
        # Check dashboard 11 pages
        pages_dir = os.path.join(dashboard, "src", "pages")
        self.assertTrue(os.path.isdir(pages_dir))
        pages = [f for f in os.listdir(pages_dir) if f.endswith(".tsx")]
        self.assertEqual(len(pages), 11, f"Expected 11 dashboard pages, found {len(pages)}")

if __name__ == "__main__":
    unittest.main()
