"""Reject artifact selectors that could read signer files or alter workflow outputs."""

import ast
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/attest.yml').read_text())


def namespace(step_name):
    step = next(item for item in WORKFLOW['jobs']['attest']['steps'] if item['name'] == step_name)
    source = step['run'].split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    module = ast.parse(source)
    module.body = [item for item in module.body if isinstance(item, ast.Import | ast.ImportFrom | ast.FunctionDef)]
    result = {}
    exec(compile(module, 'attestation-selector', 'exec'), result)
    return result


VALIDATE_EVENT = namespace('Validate the data-only interface')['validate_event']
VALIDATE = namespace('Validate the data-only interface')['validate_inputs']
SELECT = namespace('Select regular files inside the artifact')['select_files']


@pytest.fixture
def artifact(tmp_path):
    root = tmp_path / 'artifact'
    (root / 'dist').mkdir(parents=True)
    (root / 'reports').mkdir()
    (root / 'dist/package.whl').write_bytes(b'wheel')
    (root / 'dist/package.tar.gz').write_bytes(b'source')
    (root / 'reports/sbom.json').write_text('{}')
    return root


def test_provenance_and_sbom_file_selection(artifact):
    VALIDATE('123', 'dist/*', '', 'provenance')
    files, sbom = SELECT(artifact, 'dist/*', '')
    assert {Path(path).name for path in files} == {'package.whl', 'package.tar.gz'}
    assert sbom == ''
    VALIDATE('123', 'dist/*.whl', 'reports/sbom.json', 'runtime-wheel')
    files, sbom = SELECT(artifact, 'dist/*.whl', 'reports/sbom.json')
    assert len(files) == 1
    assert Path(sbom).name == 'sbom.json'


@pytest.mark.parametrize('selector', ['/etc/passwd', '../secret', 'dist/../secret', 'dist//x', '.', 'dist/./x', 'dist/!x', 'dist/[x]', 'dist/x\nINJECT=value', 'dist/x\\y'])
def test_unsafe_subject_path_is_rejected(selector):
    with pytest.raises(ValueError):
        VALIDATE('123', selector, '', 'provenance')


@pytest.mark.parametrize('sbom', ['../secret', '/etc/passwd', 'reports/*', 'reports/x\nINJECT=value'])
def test_unsafe_sbom_path_is_rejected(sbom):
    with pytest.raises(ValueError):
        VALIDATE('123', 'dist/*', sbom, 'provenance')


@pytest.mark.parametrize('identifier', ['', '0', '-1', '1,2', '12\n13', '1.0'])
def test_only_one_numeric_artifact_id(identifier):
    with pytest.raises(ValueError):
        VALIDATE(identifier, 'dist/*', '', 'provenance')


@pytest.mark.parametrize('name', ['../bundle', 'x/y', 'x\nINJECT=value', '-name', 'a' * 81])
def test_unsafe_bundle_name_is_rejected(name):
    with pytest.raises(ValueError):
        VALIDATE('123', 'dist/*', '', name)


def test_missing_subjects_and_directory_subjects_are_rejected(artifact):
    with pytest.raises(ValueError, match='between 1 and 1024'):
        SELECT(artifact, 'missing/*', '')
    with pytest.raises(ValueError, match='regular files'):
        SELECT(artifact, 'dist', '')


def test_missing_sbom_is_rejected(artifact):
    with pytest.raises(ValueError, match='regular files'):
        SELECT(artifact, 'dist/*', 'reports/missing.json')


def test_symlink_outside_selected_files_is_rejected(artifact):
    (artifact / 'reports/link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='Symlinks'):
        SELECT(artifact, 'dist/*', '')


def test_output_injection_filename_is_rejected(artifact):
    (artifact / 'dist/x\nINJECT=value').write_bytes(b'bad')
    with pytest.raises(ValueError, match='safe ASCII'):
        SELECT(artifact, 'dist/*', '')


@pytest.mark.parametrize('event', ['create', 'release', 'push', 'workflow_dispatch'])
def test_supported_source_event(event):
    VALIDATE_EVENT(event)


@pytest.mark.parametrize('event', ['pull_request', 'pull_request_target', 'repository_dispatch', 'workflow_run', 'workflow_call', ''])
def test_unsupported_source_event_is_rejected(event):
    with pytest.raises(ValueError, match='Unsupported source workflow event'):
        VALIDATE_EVENT(event)
