"""Fail-closed resume guards; fixtures never load an editor or touch repo assets."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'Tools' / filename)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value
stage = load('bb_resume_test_stage', 'stage_hlck_arena_expansion.py')
resume = load('bb_resume_test', 'resume_hlck_arena_expansion.py')


class ResumeGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(resume, 'ROOT', self.root); self.patch.start()
        self.directory = self.root / '.local/hlck/arena-expansion-stage/failed'
        self.receipt = self.directory / 'result.json'
        files = [self.root / 'Content' / ('Map%d.umap' % i) for i in range(2)] + [self.root / 'Content/Mesh.uasset']
        for i, file in enumerate(files):
            file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(('original%d' % i).encode())
        self.files = files
        self.fake = SimpleNamespace(MAPS=stage.MAPS, digest=stage.digest, plan_hash=stage.plan_hash,
            allowed_files=lambda plan: files, map_file=lambda path: files[list(stage.MAPS).index(path)])
        self.plan = {'changed_meshes': [{'name': 'SM_BB_PyramidCollision', 'sha256_after': 'a' * 64}]}
        backups = []
        for file in files:
            backup = self.directory / 'backups' / file.name
            backup.parent.mkdir(parents=True, exist_ok=True); backup.write_bytes(file.read_bytes())
            backups.append({'path': str(file), 'backup': str(backup), 'sha256': stage.digest(file)})
        self.report = {'status': 'failed', 'dry_run': False, 'plan': self.plan, 'plan_sha256': stage.plan_hash(self.plan),
            'pyramid_collision_build': {'source_sha256': 'a' * 64}, 'package_backups': backups,
            'maps': [{'path': path, 'sha256_before': stage.digest(self.fake.map_file(path)), 'geometry_before': {'passed': True}} for path in stage.MAPS]}
        stage.write(self.receipt, self.report)

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def validate(self):
        return resume.validate_failed_attempt(self.fake, str(self.receipt), self.plan)

    def test_exact_mesh_only_failure_can_resume(self):
        self.assertEqual(self.validate()[0], self.receipt.resolve())

    def test_saved_map_edit_refuses_resume(self):
        self.files[0].write_bytes(b'unrelated map edit')
        with self.assertRaises(RuntimeError): self.validate()

    def test_changed_original_backup_refuses_resume(self):
        Path(self.report['package_backups'][0]['backup']).write_bytes(b'wrong original')
        with self.assertRaises(RuntimeError): self.validate()

    def test_success_dry_run_or_prior_map_save_refused(self):
        for edit in (lambda report: report.update(status='staged'), lambda report: report.update(dry_run=True),
                     lambda report: report['maps'][0].update(sha256_after='b' * 64)):
            value = copy.deepcopy(self.report); edit(value); stage.write(self.receipt, value)
            with self.assertRaises(RuntimeError): self.validate()

    def test_changed_plan_or_unfinished_collision_import_refused(self):
        for edit in (lambda report: report.update(plan_sha256='c' * 64), lambda report: report.update(pyramid_collision_build={})):
            value = copy.deepcopy(self.report); edit(value); stage.write(self.receipt, value)
            with self.assertRaises(RuntimeError): self.validate()

    def test_missing_backup_refused(self):
        self.report['package_backups'].pop(); stage.write(self.receipt, self.report)
        with self.assertRaises(RuntimeError): self.validate()

    def test_receipt_outside_attempt_directory_refused(self):
        outside = self.root / 'Other/result.json'; stage.write(outside, self.report)
        with self.assertRaises(ValueError):
            resume.validate_failed_attempt(self.fake, str(outside), self.plan)


if __name__ == '__main__': unittest.main()
