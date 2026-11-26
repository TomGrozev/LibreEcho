"""ARM32 userspace tooling stays shared while Lidar packages an ARM64 image."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / 'build/ci'
sys.path.insert(0, str(CI))
from target_registry import load_target, userspace_tools_profile, validate_descriptor

VALIDATOR = CI / 'validate-targets.py'
TARGETS = ('radar_puffin', 'biscuit', 'lidar')


def shell_values(target):
    result = subprocess.run(
        [sys.executable, '-B', str(VALIDATOR), '--targets', target, '--shell'],
        capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


class UserspaceToolsProfileTests(unittest.TestCase):
    def test_lidar_descriptor_names_the_shared_arm32_tree(self):
        descriptor = load_target('lidar')
        self.assertEqual(descriptor['arch'], 'arm64')
        self.assertEqual(descriptor['platform']['tools_profile'], 'mt8167-arm64')
        self.assertEqual(descriptor['platform']['userspace_tools_profile'], 'mt8163-arm32')

    def test_registry_profile_matches_each_descriptor(self):
        self.assertEqual(userspace_tools_profile('lidar'), 'mt8163-arm32')
        for target in ('radar_puffin', 'biscuit'):
            expected = load_target(target)['platform']['tools_profile']
            self.assertEqual(userspace_tools_profile(target), expected)
        self.assertEqual(userspace_tools_profile('lidar'),
                         load_target('lidar')['platform']['userspace_tools_profile'])

    def test_shell_output_separates_image_and_userspace_tools(self):
        lidar = shell_values('lidar')
        self.assertEqual(lidar['TARGET'], 'lidar')
        self.assertEqual(lidar['TOOLS_PROFILE'], 'mt8167-arm64')
        self.assertEqual(lidar['USERSPACE_TOOLS_PROFILE'], 'mt8163-arm32')
        for target in ('radar_puffin', 'biscuit'):
            with self.subTest(target=target):
                values = shell_values(target)
                self.assertEqual(values['TARGET'], target)
                self.assertEqual(values['USERSPACE_TOOLS_PROFILE'], values['TOOLS_PROFILE'])
                self.assertEqual(values['USERSPACE_TOOLS_PROFILE'], 'mt8163-arm32')

    def test_lidar_descriptor_requires_the_arm32_userspace_profile(self):
        descriptor = json.loads((ROOT / 'release/targets/lidar.json').read_text())
        missing = json.loads(json.dumps(descriptor))
        del missing['platform']['userspace_tools_profile']
        with self.assertRaises(ValueError):
            validate_descriptor(missing, 'lidar')
        wrong = json.loads(json.dumps(descriptor))
        wrong['platform']['userspace_tools_profile'] = 'mt8167-arm64'
        with self.assertRaises(ValueError):
            validate_descriptor(wrong, 'lidar')

    def test_every_known_target_validates(self):
        for target in TARGETS:
            with self.subTest(target=target):
                self.assertEqual(load_target(target)['target_id'], target)


if __name__ == '__main__':
    unittest.main()
