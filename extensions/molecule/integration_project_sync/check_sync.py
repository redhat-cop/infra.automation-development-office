"""Exercise real sync tasks/modules against a local Controller API fixture."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import yaml

root = Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='ado-sync-test-') as work:
    work = Path(work)
    for case, expected_posts, expected_status in [
        ('active', 0, 'successful'), ('failed', 0, 'failed'),
        ('pending', 0, 'running'), ('different_branch', 1, 'successful'),
        ('idle', 1, 'successful'),
    ]:
        calls = []
        job = {'id': 41, 'url': '/api/controller/v2/project_updates/41/',
               'status': 'failed' if case == 'failed' else 'successful',
               'failed': case == 'failed', 'finished': '2026-01-01T00:00:01Z',
               'scm_url': 'https://git.example.test/repo.git',
               'scm_branch': 'old' if case == 'different_branch' else 'main',
               'scm_revision': 'new'}
        if case == 'pending':
            job.update(status='running', finished=None)
        project = {'id': 1, 'name': 'Example', 'scm_revision': 'old',
                   'related': {'update': '/api/controller/v2/projects/1/update/'}}
        if case != 'idle':
            project['related']['current_update'] = job['url']

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = urlsplit(self.path).path
                if path.endswith('/projects/'):
                    data = {'count': 1, 'results': [project]}
                elif path.endswith('/organizations/'):
                    data = {'count': 1, 'results': [{'id': 2, 'name': 'Example'}]}
                elif path.endswith('/project_updates/'):
                    data = {'count': 1, 'results': [job]}
                elif path.endswith('/project_updates/41/'):
                    data = job
                else:
                    raise AssertionError(path)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_POST(self):
                assert self.path.endswith('/projects/1/update/')
                calls.append(self.path)
                self.send_response(202)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(job).encode())

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        play = [{'name': 'Verify sync ' + case, 'hosts': 'localhost',
                 'connection': 'local', 'gather_facts': False,
                 'vars': {'controller_host': f'http://127.0.0.1:{server.server_port}',
                          'controller_oauthtoken': 'fixture-token',
                          'bootstrap_controller_project_sync_timeout': 1,
                          'bootstrap_controller_project_sync_result': {'results': []},
                          'bootstrap_controller_sync_project': {
                              'name': 'Example', 'organization': 'Example',
                              'scm_url': 'https://git.example.test/repo.git',
                              'scm_branch': 'main'}},
                 'tasks': [
                     {'name': 'Run source sync tasks', 'ansible.builtin.include_tasks':
                      str(root / 'roles/bootstrap_controller/tasks/sync_one_controller_project.yml')},
                     {'name': 'Check status propagated to bootstrap', 'ansible.builtin.assert':
                      {'that': [f"bootstrap_controller_project_sync_result.results[0].status == '{expected_status}'"]}},
                 ]}]
        path = work / (case + '.yml')
        path.write_text(yaml.safe_dump(play))
        env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(work / 'local'),
                   ANSIBLE_REMOTE_TEMP=str(work / 'remote'))
        proc = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                              capture_output=True, text=True, env=env)
        server.shutdown()
        server.server_close()
        if proc.returncode or len(calls) != expected_posts:
            raise AssertionError(f'{case}: launches={len(calls)}\n{proc.stdout}\n{proc.stderr}')
        print(f'PASS {case}: {len(calls)} update launches; status={expected_status}', flush=True)
