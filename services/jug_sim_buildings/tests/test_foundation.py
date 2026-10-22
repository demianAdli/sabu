"""
Sabu project
jug_sim_buildings package
test_foundation module
Verify installed startup and chassis integration.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest
from unittest.mock import patch

from jug_sim_buildings.__main__ import main
from jug_sim_buildings.logging_setup import _default_log_base


class TestFoundation(unittest.TestCase):
    def test_installed_logging_uses_state_directory_not_cwd(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'LOCALAPPDATA': directory}), \
                patch('jug_sim_buildings.logging_setup.__file__',
                      str(Path(directory) / 'Lib/site-packages/jug_sim_buildings/logging_setup.py')):
            self.assertEqual(_default_log_base(), Path(directory) / 'Sabu/jug_sim_buildings')

    def run_python(self, arguments, directory):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        return subprocess.run(
            [sys.executable, '-B', *arguments], cwd=directory, env=env,
            capture_output=True, text=True, timeout=30, check=True)

    def test_application_imports_without_flask_or_startup_side_effects(self):
        code = textwrap.dedent("""
            import sys
            import jug_sim_buildings
            import jug_sim_buildings.scenario_001
            from jug_sim_buildings.application import get_health
            assert get_health() == {
                'service': 'jug_sim_buildings', 'status': 'ok'}
            for name in ('flask', 'flask_smorest', 'sabu_chassis', 'hub'):
                assert name not in sys.modules, name
        """)
        with TemporaryDirectory() as directory:
            self.run_python(['-c', code], directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_module_help_does_not_create_logs(self):
        with TemporaryDirectory() as directory:
            result = self.run_python(
                ['-m', 'jug_sim_buildings', '--help'], directory)
            self.assertIn('--host', result.stdout)
            self.assertIn('--port', result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_module_starts_factory_with_selected_bind_address(self):
        with patch('jug_sim_buildings.api.create_app') as factory:
            self.assertEqual(main(['--host', '127.0.0.2', '--port', '5051']), 0)
        factory.assert_called_once_with()
        factory.return_value.run.assert_called_once_with(
            host='127.0.0.2', port=5051)

    def test_chassis_defaults_write_correlated_json_logs(self):
        code = textwrap.dedent("""
            import json
            import logging
            import os
            from pathlib import Path
            from unittest.mock import patch
            from sabu_chassis.logging.context import get_request_id
            from jug_sim_buildings.api import create_app
            for name in list(os.environ):
                if name.startswith('LOG_'):
                    del os.environ[name]
            service_root = Path('checkout/jug_sim_buildings').resolve()
            service_root.mkdir(parents=True)
            (service_root / 'pyproject.toml').touch()
            module_path = service_root / 'src/jug_sim_buildings/logging_setup.py'
            with patch('jug_sim_buildings.logging_setup.__file__', str(module_path)):
                app = create_app({'TESTING': True})
            response = app.test_client().get(
                '/health', headers={'X-Request-ID': 'chassis-default'})
            assert response.status_code == 200
            assert get_request_id() == '-'
            logging.shutdown()
            records = [json.loads(line) for line in (
                service_root / 'logs/jug_sim_buildings.log').read_text(
                    encoding='utf-8').splitlines()]
            access = next(r for r in records if r['msg'] == 'http_request')
            assert access['service'] == 'sim_buildings-api'
            assert access['request_id'] == 'chassis-default'
            assert access['status'] == 200
            assert access['path'] == '/health'
            assert not Path('logs').exists()
        """)
        with TemporaryDirectory() as directory:
            self.run_python(['-c', code], directory)

    def test_chassis_honors_logging_overrides_on_failed_request(self):
        code = textwrap.dedent("""
            import json
            import logging
            import os
            from pathlib import Path
            from unittest.mock import patch
            from sabu_chassis.logging.context import get_request_id
            from jug_sim_buildings.api import create_app
            for name in list(os.environ):
                if name.startswith('LOG_'):
                    del os.environ[name]
            base = Path('custom-logs').resolve()
            os.environ.update({
                'LOG_DIR_BASE': str(base),
                'LOG_FILE_NAME': 'override.jsonl',
                'LOG_SERVICE': 'custom-service',
                'LOG_ENV': 'test',
                'LOG_LEVEL': 'INFO',
                'LOG_FILE_LEVEL': 'INFO',
                'LOG_FILE_MAX_BYTES': '12345',
                'LOG_FILE_BACKUP_COUNT': '2',
            })
            app = create_app({'TESTING': True})
            file_handler = next(h for h in logging.getLogger().handlers
                                if hasattr(h, 'baseFilename'))
            assert file_handler.maxBytes == 12345
            assert file_handler.backupCount == 2
            assert file_handler.level == logging.INFO
            assert logging.getLogger().level == logging.INFO
            with patch('jug_sim_buildings.resources.health.get_health',
                       side_effect=RuntimeError('private failure')):
                response = app.test_client().get(
                    '/health', headers={'X-Correlation-ID': 'failed-request'})
            assert response.status_code == 500
            assert response.headers['X-Request-ID'] == 'failed-request'
            assert get_request_id() == '-'
            logging.shutdown()
            records = [json.loads(line) for line in (
                base / 'override.jsonl').read_text(
                    encoding='utf-8').splitlines()]
            error = next(r for r in records
                         if r['msg'] == 'unhandled_exception')
            access = next(r for r in records if r['msg'] == 'http_request')
            for record in (error, access):
                assert record['service'] == 'custom-service'
                assert record['env'] == 'test'
                assert record['request_id'] == 'failed-request'
            assert error['exc_type'] == 'RuntimeError'
            assert access['status'] == 500
            assert not Path('logs').exists()
        """)
        with TemporaryDirectory() as directory:
            self.run_python(['-c', code], directory)


if __name__ == '__main__':
    unittest.main()
