"""Exercise actual source expressions and syntax without a cluster."""
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[3]

# OpenShift Deploy RHBK must not statically import standalone (firewalld) tasks.
_rhbk_main = (ROOT / 'roles/install_rhbk/tasks/main.yml').read_text()
if 'import_tasks: install-rhbk-standalone.yml' in _rhbk_main:
    raise SystemExit(
        'FAIL: install_rhbk must use include_tasks for standalone gate '
        '(static import_tasks breaks OpenShift EE without ansible.posix)'
    )
if 'include_tasks: install-rhbk-standalone.yml' not in _rhbk_main:
    raise SystemExit('FAIL: install_rhbk missing include_tasks standalone gate')
print('PASS: install_rhbk platform gate uses include_tasks')

def read(path):
    return yaml.safe_load((ROOT / path).read_text())

def assertion(expressions):
    return {'name': 'Assert regression behavior', 'ansible.builtin.assert': {'that': expressions}}

quay = read('roles/ocp_quay/tasks/configure-quay-oidc.yml')[0]['block'][0]
service = next(t for t in read('roles/ocp_minio/tasks/install-minio.yml') if t['name'] == 'Create MinIO Service')
netbox = read('roles/netbox_oidc/defaults/main.yml')['netbox_oidc_namespace']
bookstack = read('roles/bookstack_openshift/tasks/configure-oidc.yml')
# Parse actual BookStack task syntax with Ansible, including module-option placement.
syntax = [{'hosts': 'localhost', 'gather_facts': False, 'tasks': bookstack[:1]}]
vars_ = {'rhbk_hostname': 'sso.example.test', 'rhbk_realm': 'team',
         'minio_api_port': '9000', 'minio_console_port': '9090',
         'minio_service_name': 'storage', 'name_space': 'custom-storage',
         'netbox_namespace': 'custom-netbox', 'ocp_devspaces_hostname': 'ide.apps.example.test',
         'app_namespace': 'custom-workspaces'}
tasks = [quay, assertion(["ocp_quay_oidc_issuer_url == 'https://sso.example.test/realms/team/'"]),
         {'name': 'Render Service', 'ansible.builtin.set_fact': {'rendered_service': service['kubernetes.core.k8s']['definition']}},
         {'name': 'Decode Service', 'ansible.builtin.set_fact': {'service': '{{ rendered_service | from_yaml }}'}},
         assertion(['service.spec.ports[0].port == 9000', 'service.spec.ports[1].port == 9090']),
         {'name': 'Resolve namespace', 'ansible.builtin.set_fact': {'resolved_netbox_namespace': netbox}},
         assertion(["resolved_netbox_namespace == 'custom-netbox'"]),
         {'name': 'Build CheCluster', 'ansible.builtin.import_tasks': str(ROOT / 'roles/ocp_devspaces/tasks/build-checluster.yml')},
         assertion(["ocp_devspaces_checluster_resource.metadata.namespace == 'custom-workspaces'",
                    "ocp_devspaces_checluster_spec.networking.hostname == 'ide.apps.example.test'",
                    'ocp_devspaces_checluster_spec.server is not defined'])]
with tempfile.TemporaryDirectory(prefix='ado-regressions-') as directory:
    p = Path(directory) / 'test.yml'
    p.write_text(yaml.safe_dump(syntax))
    subprocess.run(['ansible-playbook', '-i', 'localhost,', str(p), '--syntax-check'], check=True)
    p.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False, 'vars': vars_, 'tasks': tasks}]))
    subprocess.run(['ansible-playbook', '-i', 'localhost,', str(p)], check=True)
# OpenShift Deploy RHBK must not statically import standalone (firewalld) tasks.
rhbk_main = (ROOT / 'roles/install_rhbk/tasks/main.yml').read_text()
if 'import_tasks: install-rhbk-standalone.yml' in rhbk_main:
    raise SystemExit(
        'FAIL: install_rhbk must use include_tasks for standalone gate '
        '(static import_tasks breaks OpenShift EE without ansible.posix)'
    )
if 'include_tasks: install-rhbk-standalone.yml' not in rhbk_main:
    raise SystemExit('FAIL: install_rhbk missing include_tasks standalone gate')
print('PASS: OIDC fallback, integer ports, namespace override, CheCluster v2 and BookStack syntax')
