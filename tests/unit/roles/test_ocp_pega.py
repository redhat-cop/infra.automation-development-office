"""Disconnected image validation rejects public, mutable and spoofed references."""
import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "pega_images", Path(__file__).parents[3] / "roles/ocp_pega/files/validate_images.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestPegaOfflineImages(unittest.TestCase):
    def test_accepts_pinned_private_images_in_init_and_regular_containers(self):
        document = {"spec": {"initContainers": [{"image": "mirror.example:5000/tool:1"}],
                             "containers": [{"image": "mirror.example:5000/pega@sha256:abc"}]}}
        assert not MODULE.validate([document], ["mirror.example:5000"])

    def test_rejects_public_hook_image_even_with_private_workload(self):
        documents = [{"image": "mirror.example/pega:1"},
                     {"kind": "Job", "spec": {"containers": [{"image": "docker.io/tool:1"}]}}]
        assert MODULE.validate(documents, ["mirror.example"])

    def test_rejects_registry_prefix_spoof_and_unpinned_images(self):
        for ref in ["mirror.example.evil/pega:1", "mirror.example/pega:latest",
                    "mirror.example/pega", "pega:1"]:
            assert MODULE.validate([{"image": ref}], ["mirror.example"])

    def test_rejects_empty_render(self):
        assert MODULE.validate([None, {"kind": "Secret"}], ["mirror.example"])


if __name__ == "__main__":
    unittest.main()
