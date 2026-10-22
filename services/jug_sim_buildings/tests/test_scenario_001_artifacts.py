"""
Sabu project
jug_sim_buildings package
test_scenario_001_artifacts module
Verify artifact retention and scoped temporary-file cleanup.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from jug_sim_buildings.scenario_001.run_artifacts import RunArtifacts


class TestRunArtifacts(unittest.TestCase):
    def test_cleanup_preserves_required_outputs_completed_runs_and_external_artifacts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / 'registered-upstream.geojson'
            upstream.write_bytes(b'upstream original')
            older = RunArtifacts(root / 'runs')
            older.write_json('run.json', {'status': 'succeeded'})
            current = RunArtifacts(root / 'runs')
            required = (
                'input/standardized.geojson', 'retained.geojson', 'records.json',
                'source_records.jsonl', 'statistics.json', 'source_crs.json', 'run.json',
                'reports/summary.md', 'reports/duplicates.json', 'responses/preprocessing.body',
                'responses/uniquification.body', 'evidence/failure.json',
            )
            for name in required:
                current.write_text(name, f'preserve {name}')
            current.temporary('uniquification-request.json').write_text('scratch')
            current.temporary('pending.tmp').write_text('partial derived write')
            # An untracked file is never swept up by a broad cleanup pattern.
            current.path('tmp/untracked.tmp').write_text('leave alone')
            self.assertEqual(current.cleanup(failed=False), [])
            for name in required:
                self.assertEqual(current.path(name).read_text(), f'preserve {name}')
            self.assertEqual([p.name for p in current.path('tmp').iterdir()], ['untracked.tmp'])
            self.assertEqual(upstream.read_bytes(), b'upstream original')
            self.assertEqual(json.loads(older.path('run.json').read_text())['status'], 'succeeded')

    def test_failed_download_is_quarantined_and_zero_length_scratch_is_removed(self):
        with TemporaryDirectory() as directory:
            run = RunArtifacts(directory)
            run.temporary('download.part').write_bytes(b'partial download')
            run.temporary('uniquification-request.json').write_bytes(b'')
            self.assertEqual(run.cleanup(failed=True), [])
            self.assertEqual(run.path('evidence/standardized.partial').read_bytes(), b'partial download')
            self.assertEqual(list(run.path('tmp').iterdir()), [])

    def test_existing_directory_and_path_escape_are_rejected_without_changes(self):
        with TemporaryDirectory() as directory:
            run = RunArtifacts(directory, 'b' * 32)
            run.write_text('run.json', 'original')
            with self.assertRaises(FileExistsError):
                RunArtifacts(directory, 'b' * 32)
            for value in ('../outside', 'C:/outside', '/outside'):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    run.path(value)
            with self.assertRaises(ValueError):
                run.temporary('../outside')
            self.assertEqual(run.path('run.json').read_text(), 'original')

    def test_redirected_scratch_parent_is_never_deleted(self):
        with TemporaryDirectory() as directory:
            run = RunArtifacts(directory)
            path = run.temporary('scratch.tmp')
            path.write_bytes(b'sensitive evidence')
            original_resolve = Path.resolve

            def redirected(candidate, *args, **kwargs):
                if candidate == path:
                    return Path(directory) / 'outside.tmp'
                return original_resolve(candidate, *args, **kwargs)

            with patch.object(Path, 'resolve', redirected):
                errors = run.cleanup(failed=True)
            self.assertEqual(len(errors), 1)
            self.assertIn('redirected', errors[0]['message'])
            self.assertEqual(path.read_bytes(), b'sensitive evidence')

    def test_cleanup_errors_preserve_locked_files_and_continue_other_cleanup(self):
        with TemporaryDirectory() as directory:
            run = RunArtifacts(directory)
            locked = run.temporary('locked.tmp')
            locked.write_text('locked evidence')
            removable = run.temporary('removable.tmp')
            removable.write_text('scratch')
            original_unlink = Path.unlink

            def unlink(candidate, *args, **kwargs):
                if candidate == locked:
                    raise PermissionError('locked')
                return original_unlink(candidate, *args, **kwargs)

            with patch.object(Path, 'unlink', unlink):
                errors = run.cleanup(failed=True)
            self.assertEqual(len(errors), 1)
            self.assertTrue(locked.exists())
            self.assertFalse(removable.exists())

    def test_failed_quarantine_keeps_partial_download_in_place(self):
        with TemporaryDirectory() as directory:
            run = RunArtifacts(directory)
            partial = run.temporary('download.part')
            partial.write_bytes(b'useful')
            with patch.object(Path, 'replace', side_effect=PermissionError('locked')):
                errors = run.cleanup(failed=True)
            self.assertEqual(len(errors), 1)
            self.assertEqual(partial.read_bytes(), b'useful')
