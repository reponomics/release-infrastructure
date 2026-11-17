"""The shared signer accepts data without giving callers control of its code."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/attest.yml').read_text())


def test_only_data_inputs_and_signed_artifact_output():
    trigger = WORKFLOW.get('on', WORKFLOW.get(True))
    assert set(trigger) == {'workflow_call'}
    assert set(trigger['workflow_call']['inputs']) == {
        'artifact-id', 'subject-path', 'sbom-path', 'attestation-name'
    }
    assert set(trigger['workflow_call']['outputs']) == {'attestations'}


def test_signer_is_fresh_and_has_no_caller_code_or_custom_provenance():
    assert set(WORKFLOW['jobs']) == {'attest'}
    job = WORKFLOW['jobs']['attest']
    assert job['permissions'] == {'contents': 'read', 'id-token': 'write', 'attestations': 'write'}
    assert job['runs-on'] == 'ubuntu-24.04'
    assert 'secrets' not in str(job)
    actions = [step for step in job['steps'] if 'uses' in step]
    assert {step['uses'].split('@')[0] for step in actions} == {
        'actions/download-artifact', 'actions/attest', 'actions/upload-artifact'
    }
    download, attest, upload = actions
    assert download['with'] == {
        'artifact-ids': '${{ inputs.artifact-id }}', 'path': 'artifact', 'merge-multiple': True
    }
    assert set(attest['with']) == {'subject-path', 'sbom-path'}
    assert 'inputs' not in str(attest['with'])
    assert upload['with']['path'] == 'attestations/'
    for step in job['steps']:
        assert '${{' not in step.get('run', '')
        assert 'continue-on-error' not in step


def test_every_action_is_pinned_and_workflow_defaults_are_read_only():
    for path in (ROOT / '.github/workflows').glob('*.yml'):
        workflow = yaml.safe_load(path.read_text())
        assert workflow['permissions'] == {'contents': 'read'}
        for job in workflow['jobs'].values():
            for step in job.get('steps', []):
                if 'uses' in step:
                    assert re.fullmatch(r'[^@]+@[0-9a-f]{40}', step['uses'])
