#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
from importlib.util import module_from_spec, spec_from_file_location


def load_module():
    spec = spec_from_file_location(
        "fetch_public_deps", ROOT / "build/ci/fetch-public-deps.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODELS = {
    "alexa": "9011a8155b04de858c48038529235cbc0e42e9fca05a55bf588cb80a653a723b",
    "okay_nabu": "0689abe1912a95a3318a0d8cb2e67bad0cbcfe3e24dd6e050c75debddfb6f891",
    "hey_jarvis": "21a7976add39ee24ec96c63d96b7aaa18e24d1d9824b963e451da8feb4b78b77",
    "hey_mycroft": "c2a9b6ed51182db72e014781d5a4ece1929dc232a40b5b4be384f0295f0e1571",
    "vad": "7aa4db6d5fb7c5358609f6931e7847d303c16a43d178638bc14104f50d7eff5f",
}


class WakeWordInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.records = {
            record["name"]: record
            for record in json.loads(
                (ROOT / "build/inputs/public-inputs.json").read_text()
            )["inputs"]
        }

    def test_tflite_micro_is_pinned_by_commit(self) -> None:
        record = self.records["tflite-micro-source"]
        self.assertEqual(record["kind"], "source-git")
        self.assertEqual(record["redistribution"], "source-git-pinned")
        self.assertEqual(
            record["commit"], "5d5a2e9afce50bf2dc75f5e8b10776aef13157b6")
        self.assertEqual(record["license"], "Apache-2.0")

    def test_frontend_sources_pin_their_digests(self) -> None:
        expected = {
            "flatbuffers-source":
                "9102253214dea6ae10c2ac966ea1ed2155d22202390b532d1dea64935c518ada",
            "kissfft-source":
                "1782cd90f036765523c72b521ecb1df321883d3cfca65097ba139ff60e696051",
            "eyalroz-printf-source":
                "2886f161744f740d4d857962d18839fae65c53e8411abe41934def0f9bf4a670",
        }
        for name, digest in expected.items():
            record = self.records[name]
            self.assertEqual(record["kind"], "source-archive-tree")
            self.assertEqual(record["sha256"], digest)
            self.assertEqual(record["redistribution"], "cleared")

    def test_model_source_pins_five_v2_models(self) -> None:
        record = self.records["micro-wake-word-models-source"]
        self.assertEqual(record["kind"], "source-git")
        self.assertEqual(
            record["commit"], "40ff33f57f8fc6ad71a75ef085abbf742495b225")
        pins = {Path(pin["path"]).stem: pin["sha256"]
                for pin in record["models"]}
        self.assertEqual(pins, MODELS)
        self.assertTrue(all(
            pin["path"].startswith("models/v2/")
            for pin in record["models"]))

    def test_model_pin_without_digest_fails_load(self) -> None:
        record = dict(self.records["micro-wake-word-models-source"])
        record["name"] = "bad-models"
        record["models"] = [dict(record["models"][0], sha256="not-a-digest")]
        inventory = {
            "schema": "libreecho-public-inputs-v1",
            "inputs": [record],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inputs.json"
            path.write_text(json.dumps(inventory))
            with self.assertRaises(ValueError):
                self.module.load(path)

    def test_wake_tflm_is_wired_into_the_build(self) -> None:
        build = (ROOT / "build/build.sh").read_text()
        for variable in (
            "WAKE_TFLM_SOURCE", "WAKE_TFLM_FLATBUFFERS_SOURCE",
            "WAKE_TFLM_KISSFFT_SOURCE", "WAKE_TFLM_PRINTF_SOURCE",
            "WAKE_TFLM_MODELS_ROOT", "WAKE_TFLM_PREFIX",
            "build_micro_wake_word.sh", "wake-tflm",
        ):
            self.assertIn(variable, build)


if __name__ == "__main__":
    unittest.main()
