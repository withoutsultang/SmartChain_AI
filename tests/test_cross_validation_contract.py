"""Run with python -m unittest discover -s tests -v; no API calls or model loading."""
import importlib.util
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
schema = load("run_contract", "apps/ai_run_api/app/schemas/run.py")
cross = load("compliance_cross", "apps/ai_run_api/app/engines/compliance/cross_validators.py")

class CrossValidationContractTest(unittest.TestCase):
    def test_real_cross_validator_counts_survive_response_roundtrip(self):
        output = cross.cross_validate_slot({
            "compliance.education.attendance": [{"text": "김민준 서명\n이서연 서명"}],
            "compliance.education.photo": [{"extras": {"person_count": 2}}],
        })
        self.assertEqual(len(output), 1)
        slot = schema.SlotResult.model_validate(output[0])
        response = schema.SubmitResponse(package_id="test", risk_level="LOW",
            verdict="PASS", why="일치", slot_results=[slot],
            extras={"counts": [2, 2], "matched": True, "context": {"source": "test"}})
        restored = schema.SubmitResponse.model_validate_json(response.model_dump_json())
        self.assertEqual(restored.slot_results[0].extras["attendance_count"], 2)
        self.assertIsInstance(restored.slot_results[0].extras["photo_count"], int)
        self.assertEqual(restored.extras["counts"], [2, 2])

    def test_missing_photo_does_not_create_cross_result(self):
        self.assertEqual(cross.cross_validate_slot({
            "compliance.education.attendance": [{"text": "김민준 서명"}]}), [])

    def test_slot_default_collections_are_independent(self):
        first = schema.SlotResult(slot_name="a", verdict="PASS")
        second = schema.SlotResult(slot_name="b", verdict="PASS")
        first.extras["count"] = 1
        first.reasons.append("example")
        self.assertEqual(second.extras, {})
        self.assertEqual(second.reasons, [])

if __name__ == "__main__":
    unittest.main()
