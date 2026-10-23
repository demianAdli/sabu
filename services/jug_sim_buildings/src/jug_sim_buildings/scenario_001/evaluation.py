"""
Sabu project
jug_sim_buildings package
evaluation module
Record bounded provenance and evidence for four evaluation criteria.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from importlib import metadata
import platform
from pathlib import Path

from .contracts import load_json, require
from .run_artifacts import file_digest


def capture_provenance(artifacts, config):
    packages = {}
    for name in ('jug_sim_buildings', 'sabu-chassis', 'requests', 'marshmallow', 'citygisoo'):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    report = {'local_python': platform.python_version(), 'local_packages': packages,
              'configuration': config.as_dict(), 'upstream': {'status': 'unavailable'},
              'limitations': [
                  'Local installed distributions do not establish remote service/library versions.',
                  'LCA JSON does not expose cache-hit status, request hash, catalogue revisions or calculation settings.',
                  'Declared provenance must be linked to correlated service logs and cache evidence; it is not runtime verification.']}
    if config.evaluation_provenance_path:
        source = Path(config.evaluation_provenance_path)
        payload = load_json(source)
        require(isinstance(payload, dict), 'Evaluation provenance must be a JSON object.')
        data = source.read_bytes()
        with artifacts.path('reports/operator_provenance.json').open('xb') as stream:
            stream.write(data)
        report['upstream'] = {'status': 'operator_supplied', 'declarations': payload,
                              'source': str(source), 'artifact': 'reports/operator_provenance.json',
                              **file_digest(artifacts.path('reports/operator_provenance.json'))}
    artifacts.write_json('reports/provenance.json', report)


def write_evaluation(artifacts, state):
    stages = state.get('stage_outcomes', [])
    complete = state.get('status') in ('succeeded', 'succeeded_with_cleanup_errors') and state.get('lca', {}).get('status') == 'succeeded'
    failed = state.get('status') == 'failed'
    report = {'schema_version': 1, 'run_id': artifacts.run_id, 'fsa': state['fsa'],
              'status': state['status'], 'criteria': {
                  'end_to_end_execution': {'status': 'passed' if complete else ('failed' if failed else 'not_evaluated'),
                                           'evidence': ['run.json', 'reports/stages.json', 'responses/lca.http.json']},
                  'contract_compliance': {'status': 'passed' if complete else 'incomplete',
                                          'evidence': ['lca/reconciliation.json', 'reports/stages.json']},
                  'traceability': {'status': 'passed' if complete and state.get('trace', {}).get('status') == 'complete' else 'incomplete',
                                   'evidence': ['trace/records.jsonl', 'trace/reconciliation.json']},
                  'failure_handling': {'status': 'failure_recorded' if failed else 'not_exercised',
                                       'evidence': ['run.json', 'reports/stages.json'],
                                       'note': 'Controlled injected-failure tests are separate evidence; a successful real run does not prove failure handling.'}},
              'error': state.get('error'), 'cleanup_errors': state.get('cleanup_errors', []),
              'provenance': 'reports/provenance.json',
              'artifacts': {k: v for k, v in state.get('artifacts', {}).items() if k != 'reports/evaluation.json'},
              'timeout_policy': 'No automatic processing retries; timeout does not establish upstream cancellation.'}
    artifacts.write_json('reports/stages.json', stages)
    artifacts.write_json('reports/evaluation.json', report)
    return report
