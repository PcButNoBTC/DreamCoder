import os
import unittest

from models.huggingface import HuggingFaceModel


class HuggingFaceRoutingTests(unittest.TestCase):
    def test_uses_current_router_defaults(self):
        old_inference = os.environ.pop("HF_INFERENCE_BASE_URL", None)
        old_router = os.environ.pop("HF_ROUTER_BASE_URL", None)
        try:
            self.assertEqual(
                HuggingFaceModel._inference_base_url(),
                "https://router.huggingface.co/hf-inference",
            )
            self.assertEqual(
                HuggingFaceModel._router_base_url(),
                "https://router.huggingface.co/v1",
            )
        finally:
            if old_inference is not None:
                os.environ["HF_INFERENCE_BASE_URL"] = old_inference
            if old_router is not None:
                os.environ["HF_ROUTER_BASE_URL"] = old_router

    def test_network_failures_are_token_independent(self):
        self.assertTrue(HuggingFaceModel._is_network_error(RuntimeError("[Errno 11001] getaddrinfo failed")))
        self.assertTrue(HuggingFaceModel._is_network_error(RuntimeError("Temporary failure in name resolution")))
        self.assertFalse(HuggingFaceModel._is_network_error(RuntimeError("401 Client Error: Unauthorized")))


if __name__ == "__main__":
    unittest.main()
