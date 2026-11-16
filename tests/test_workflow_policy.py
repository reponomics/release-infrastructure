"""The reusable workflow owns its build and never signs caller-supplied artifacts."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/python-release.yml').read_text())
JOBS = WORKFLOW['jobs']


def test_only_tag_and_prerelease_are_caller_inputs():
    trigger = WORKFLOW.get('on', WORKFLOW.get(True))
    assert set(trigger) == {'workflow_call'}
    assert set(trigger['workflow_call']['inputs']) == {'tag', 'prerelease'}
    assert set(trigger['workflow_call']['outputs']) == {'candidate', 'attestations'}


def test_build_has_no_signing_permissions_and_uses_exact_caller_commit():
    assert WORKFLOW['permissions'] == {'contents': 'read'}
    build = JOBS['build']
    assert build['permissions'] == {'contents': 'read'}
    assert 'secrets' not in str(build)
    guard = build['if']
    assert "github.repository == 'reponomics/best-practices-mcp'" in guard
    assert "github.event_name == 'workflow_dispatch'" in guard
    assert 'github.workflow_ref ==' in guard
    assert 'github.ref == format' in guard
    checkout = build['steps'][0]
    assert checkout['with']['ref'] == '${{ github.sha }}'
    assert checkout['with']['persist-credentials'] is False
    assert any(s.get('run') == 'make validate' for s in build['steps'])


def test_attestation_uses_only_this_builds_artifact_without_executing_source():
    attest = JOBS['attest']
    assert attest['needs'] == 'build'
    assert attest['permissions'] == {'contents': 'read', 'id-token': 'write', 'attestations': 'write'}
    assert attest['runs-on'] == 'ubuntu-24.04'
    steps = attest['steps']
    assert steps[0]['with']['artifact-ids'] == '${{ needs.build.outputs.candidate }}'
    assert not any('checkout@' in s.get('uses', '') for s in steps)
    assert not any('pypi-publish@' in s.get('uses', '') for s in steps)
    assert not any('secrets' in str(s) for s in steps)
    assert steps[1]['name'] == 'Verify candidate identities and checksums'
    assert len([s for s in steps if s.get('uses', '').startswith('actions/attest@')]) == 3


def test_every_action_is_pinned_and_workflow_defaults_are_read_only():
    for path in (ROOT / '.github/workflows').glob('*.yml'):
        workflow = yaml.safe_load(path.read_text())
        assert workflow['permissions'] == {'contents': 'read'}
        for job in workflow['jobs'].values():
            for step in job.get('steps', []):
                if 'uses' in step:
                    assert re.fullmatch(r'[^@]+@[0-9a-f]{40}', step['uses'])


def test_scan_failure_blocks_bundle_and_both_distribution_inventories_are_scanned():
    steps = {step['name']: step for step in JOBS['build']['steps']}
    bundle = steps['Assemble the successful release bundle']
    assert 'if' not in bundle
    assert 'continue-on-error' not in bundle
    vulnerability = steps['Scan candidate and tooling dependencies for vulnerabilities']
    licenses = steps['Check candidate and tooling licenses']
    for scan in (vulnerability, licenses):
        assert 'continue-on-error' not in scan
        for kind in ('wheel', 'sdist'):
            assert f'runtime-{kind}.inventory.json' in scan['with']['scan-args']
    assert 'stdlib-inventory.json' in vulnerability['with']['scan-args']
    assert 'stdlib-inventory.json' not in licenses['with']['scan-args']
