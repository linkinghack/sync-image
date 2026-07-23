import unittest
from unittest.mock import mock_open, patch

import sync


class ImagePathTests(unittest.TestCase):
    def test_target_name_preserves_source_path_by_default(self):
        self.assertEqual(
            sync.get_target_image_name("quay.io/calico/node:v3.31.4"),
            "calico/node:v3.31.4",
        )

    def test_target_name_can_drop_source_path(self):
        self.assertEqual(
            sync.get_target_image_name(
                "quay.io/calico/charts/tigera-operator:v3.31.4",
                preserve_source_path=False,
            ),
            "tigera-operator:v3.31.4",
        )

    def test_invalid_image_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid image reference"):
            sync.get_target_image_name("node:v3.31.4")

    def test_no_preserve_source_path_argument_disables_preservation(self):
        parsed = sync.arg_parser.parse_args(
            [
                "-r",
                "10.102.32.251:1121/calico",
                "--no-preserve-source-path",
            ]
        )

        self.assertFalse(parsed.preserve_source_path)

    @patch("sync.execute_template_script")
    def test_multi_arch_cache_list_uses_flat_target_names(self, execute_script):
        tagged_images = sync.cache_images_locally(
            [
                "quay.io/calico/node:v3.31.4",
                "quay.io/calico/charts/tigera-operator:v3.31.4",
            ],
            "10.102.32.251:1121/calico",
            "docker",
            True,
            "linux/amd64",
            preserve_source_path=False,
        )

        self.assertEqual(
            tagged_images,
            [
                "10.102.32.251:1121/calico/node:v3.31.4-arm64",
                "10.102.32.251:1121/calico/node:v3.31.4-amd64",
                "10.102.32.251:1121/calico/tigera-operator:v3.31.4-arm64",
                "10.102.32.251:1121/calico/tigera-operator:v3.31.4-amd64",
            ],
        )
        self.assertEqual(execute_script.call_count, 2)
        self.assertTrue(
            all(call.args[-1] is False for call in execute_script.call_args_list)
        )

    @patch("sync.execute_template_script")
    def test_single_arch_cache_list_does_not_include_template_markers(
        self,
        execute_script,
    ):
        tagged_images = sync.cache_images_locally(
            ["quay.io/calico/node:v3.31.4"],
            "10.102.32.251:1121/calico",
            "docker",
            False,
            "linux/amd64",
            preserve_source_path=False,
        )

        self.assertEqual(
            tagged_images,
            ["10.102.32.251:1121/calico/node:v3.31.4"],
        )
        execute_script.assert_called_once()

    @patch("sync.subprocess.call")
    @patch("builtins.open", new_callable=mock_open)
    def test_flattening_changes_target_but_not_source_image(
        self,
        open_file,
        subprocess_call,
    ):
        sync.execute_template_script(
            "quay.io/calico/node:v3.31.4",
            sync.tmpl_cache_locally
            .replace("${MULTI_ARCH}", "false")
            .replace("${TARGET_ARCH}", "linux/amd64"),
            "10.102.32.251:1121/calico",
            "docker",
            preserve_source_path=False,
        )

        script = open_file().write.call_args.args[0]
        self.assertIn(
            "docker pull --platform=$TARGET_ARCH quay.io/calico/node:v3.31.4",
            script,
        )
        self.assertIn(
            "docker tag  quay.io/calico/node:v3.31.4  "
            "10.102.32.251:1121/calico/node:v3.31.4",
            script,
        )
        self.assertNotIn(
            "10.102.32.251:1121/calico/calico/node:v3.31.4",
            script,
        )
        subprocess_call.assert_called_once_with(["bash", "tmp.sh"])


if __name__ == "__main__":
    unittest.main()
