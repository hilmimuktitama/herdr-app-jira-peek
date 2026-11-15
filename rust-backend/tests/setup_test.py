"""Rust setup contract checks; the independent Python oracle is left intact."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('oracle', ROOT / 'tests/setup_test.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class SetupTests(oracle.SetupTests):
    def call(self, *args):
        result = subprocess.run([os.environ['JIRA_PEEK_PRODUCTION_BINARY'], 'setup', *map(str, args)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout), result.stdout


# These oracle cases invoke a fake curl executable or patch Python internals.
# Their Rust equivalents use real libcurl in setup_transport_test.py;
# retain the originals unchanged in the independent Python suite.
for name in (
    'test_save_verifies_then_activates_compatible_config_without_token_exposure',
    'test_http_failures_preserve_config_and_remove_candidate_credential',
    'test_destination_normalizes_case_and_email_apostrophe_round_trips',
    'test_commit_point_failure_semantics',
    'test_cloud_id_routes_to_api_host_and_token_validation_rejects_netrc_controls',
    'test_scoped_site_mismatch_or_unverifiable_site_preserves_previous_connection',
    'test_runtime_site_verifier_uses_only_the_configured_origin_without_authentication',
    'test_successful_replacement_removes_only_the_previous_managed_credential',
):
    setattr(SetupTests, name, None)

if __name__ == '__main__':
    unittest.main()
