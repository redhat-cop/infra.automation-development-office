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

install_aap_defaults = read('roles/install_aap/defaults/main.yml')
if str(install_aap_defaults.get('aap_ocp_install_license_mode', '')).lower() != 'none':
    raise SystemExit('FAIL: install_aap must default license_mode to none')
if install_aap_defaults.get('aap_ocp_install_license_only') is not False:
    raise SystemExit('FAIL: install_aap must default license_only to false')
openshift_txt = (ROOT / 'roles/install_aap/tasks/openshift.yml').read_text()
if 'accept_unlicensed_platform.yml' not in openshift_txt:
    raise SystemExit(
        'FAIL: install_aap must accept an unlicensed platform when license is deferred'
    )
if 'activate_license.yml' not in openshift_txt:
    raise SystemExit('FAIL: install_aap missing activate_license include')
accept_txt = (ROOT / 'roles/install_aap/tasks/accept_unlicensed_platform.yml').read_text()
if 'aap_ocp_install_license_mode' not in accept_txt:
    raise SystemExit('FAIL: accept_unlicensed_platform must gate on license_mode')
print('PASS: install_aap license is optional after install')
controller_main = (ROOT / 'roles/bootstrap_controller/tasks/main.yml').read_text()
if 'bootstrap_controller_aap_full_install_during_bootstrap' not in controller_main:
    raise SystemExit('FAIL: playbook generation must key off full AAP install, not license-only')
jt_gen = (ROOT / 'roles/bootstrap_controller/tasks/generate_aap_configs.yml').read_text()
if 'bootstrap_controller_aap_full_install_during_bootstrap' not in jt_gen:
    raise SystemExit('FAIL: Install AAP JT skip must be full-install only')
env_main = (ROOT / 'roles/bootstrap_generate_env_vars/tasks/main.yml').read_text()
if 'Include AAP playbook/JT when Install AAP or license attach is requested' not in env_main:
    raise SystemExit('FAIL: license-only attach must add aap to playbook/JT selectors')
print('PASS: license-only attach keeps playbooks and JT')
overlay_txt = (
    ROOT / 'roles/bootstrap_generate_env_vars/files/overlay_preflight_component_values.py'
).read_text()
if 'vars_data["install_aap_target"] = install_target' not in overlay_txt:
    raise SystemExit('FAIL: overlay must write install_aap_target from preflight')
if 'aap_setup_prep_inv_nodes' not in overlay_txt:
    raise SystemExit('FAIL: overlay must emit aap_setup_prep_inv_nodes for RHEL install')
if 'if install_target != "rhel":' not in overlay_txt:
    raise SystemExit('FAIL: overlay must skip OpenShift AAP CR vars on RHEL install')
if 'bootstrap_controller_aap_install_target' not in controller_main:
    raise SystemExit('FAIL: bootstrap_controller must resolve AAP install_target')
if 'ado-aap-rhel-install-bootstrap.jt.yml' not in jt_gen:
    raise SystemExit('FAIL: AAP component map must include the RHEL install JT')
playbook_gen = (ROOT / 'roles/bootstrap_generate_playbook_repo/tasks/main.yml').read_text()
if 'ado-aap-rhel-install-bootstrap.yml' not in playbook_gen:
    raise SystemExit('FAIL: playbook repo must drop the unused AAP install target')
print('PASS: Install AAP can target OpenShift or standalone RHEL')
pub_one = (ROOT / 'roles/bootstrap_controller/tasks/publish_one_preflight_collection.yml').read_text()
if 'bootstrap_controller_hub_pub_exist_repos' not in pub_one:
    raise SystemExit('FAIL: additional Hub publish must check more than validated')
if 'bootstrap_controller_hub_reserved_namespaces' not in pub_one:
    raise SystemExit('FAIL: additional Hub publish must skip reserved redhat namespace')
if 'Skip reserved Hub namespace' not in pub_one:
    raise SystemExit('FAIL: additional Hub publish missing reserved-namespace skip')
print('PASS: additional Hub collections skip existing redhat namespace/content')
apply_aap = (ROOT / 'roles/bootstrap_controller/tasks/apply_aap_25_plus.yml').read_text()
if 'Check whether infra.ado already exists in validated' not in apply_aap:
    raise SystemExit('FAIL: infra.ado skip-if-exists check missing')
if '502, 503, 504' not in apply_aap:
    raise SystemExit('FAIL: infra.ado skip-if-exists must retry Hub 502/503/504')
if 'bootstrap_controller_hub_exist_check_retries' not in apply_aap:
    raise SystemExit('FAIL: infra.ado skip-if-exists must use exist_check retries')
if '502, 503, 504' not in pub_one:
    raise SystemExit('FAIL: additional Hub exist-check must accept 502/503/504')
print('PASS: Hub skip-if-exists retries on 503')
harden_defaults = read('roles/ocp_aap_hub_harden/defaults/main.yml')
if harden_defaults.get('ocp_aap_hub_harden_separate_database') is not True:
    raise SystemExit('FAIL: ocp_aap_hub_harden must default separate_database to true')
if str(harden_defaults.get('ocp_aap_hub_harden_namespace') or '') != '':
    raise SystemExit('FAIL: ocp_aap_hub_harden namespace must default empty for discover')
discover_txt = (ROOT / 'roles/ocp_aap_hub_harden/tasks/discover.yml').read_text()
if 'ocp_aap_hub_harden_already_separated' not in discover_txt:
    raise SystemExit('FAIL: discover must detect already-separated Hub Postgres')
separate_txt = (ROOT / 'roles/ocp_aap_hub_harden/tasks/separate_database.yml').read_text()
if 'ocp_aap_hub_harden_postgres_secret' not in separate_txt:
    raise SystemExit('FAIL: separate_database must write the unmanaged Hub DB secret')
if str(harden_defaults.get('ocp_aap_hub_harden_postgres_secret') or '') != 'external-hub-postgres-configuration':
    raise SystemExit('FAIL: dedicated Hub secret must default to external-hub-postgres-configuration')
cron_txt = (ROOT / 'roles/ocp_aap_hub_harden/tasks/install_cronjob.yml').read_text()
if 'AAP_CR' not in cron_txt or 'HUB_CR' not in cron_txt:
    raise SystemExit('FAIL: Hub stability CronJob must use discovered AAP/Hub CR names')
playbook_defaults = (ROOT / 'roles/bootstrap_generate_playbook_repo/defaults/main.yml').read_text()
if 'ado-aap-hub-harden-bootstrap.yml' not in playbook_defaults:
    raise SystemExit('FAIL: playbook repo must ship ado-aap-hub-harden-bootstrap.yml')
if 'aap_hub_harden:' not in jt_gen or 'ado-aap-hub-harden-bootstrap.jt.yml' not in jt_gen:
    raise SystemExit('FAIL: AAP component map must include the Hub harden JT')
if 'Include Hub dedicated-Postgres playbook/JT when AAP Tools option is selected' not in env_main:
    raise SystemExit('FAIL: env vars must add aap_hub_harden from dedicated_hub_postgres')
if 'if "dedicated_hub_postgres" in aap_options:' not in overlay_txt:
    raise SystemExit('FAIL: overlay must write vars_aap_hub_harden from AAP tools option')
if 'vars_aap_hub_harden.yml' not in overlay_txt:
    raise SystemExit('FAIL: overlay must emit vars_aap_hub_harden.yml')
print('PASS: dedicated Hub Postgres role + preflight AAP tools option')
cv_jt = (ROOT / 'roles/bootstrap_controller/files/job_templates/ado-satellite-content-view-bootstrap.jt.yml').read_text()
if "inventory: '{{ bootstrap_controller_inventory_name }}'" not in cv_jt:
    raise SystemExit('FAIL: Satellite content-view JT must use the local bootstrap inventory')
if 'bootstrap_controller_satellite_inventory_name' in cv_jt:
    raise SystemExit('FAIL: Satellite content-view JT must not require Satellite-Server-Inventory')
cv_pb = (
    ROOT / 'roles/bootstrap_generate_playbook_repo/files/playbooks/satellite/ado-manage-content-view-bootstrap.yml'
).read_text()
if 'hosts: localhost' not in cv_pb:
    raise SystemExit('FAIL: Satellite content-view playbook must run on localhost')
aap_cfg = (ROOT / 'roles/bootstrap_generate_env_vars/templates/aap_config_vars.yml.j2').read_text()
if 'if satellite_server_inventory_needed' not in aap_cfg:
    raise SystemExit('FAIL: Satellite-Server-Inventory must be created only for install/OIDC')
print('PASS: Satellite content-view uses local inventory when client/RHEL/patching is selected')
accept_play = [{
    'hosts': 'localhost',
    'connection': 'local',
    'gather_facts': False,
    'vars': {
        'aap_ocp_install_license_mode': 'none',
        'aap_ocp_install_platform_route': 'https://aap.apps.example.test',
        'ansible_failed_task': {
            'name': 'install-platform | Wait for operator to create the automation controller route',
        },
        'ansible_failed_result': {'msg': 'Timeout waiting for route'},
    },
    'tasks': [{
        'name': 'Accept deferred license at gateway',
        'ansible.builtin.include_tasks': str(
            ROOT / 'roles/install_aap/tasks/accept_unlicensed_platform.yml'
        ),
    }],
}]
with tempfile.TemporaryDirectory(prefix='ado-install-aap-license-') as directory:
    p = Path(directory) / 'accept.yml'
    p.write_text(yaml.safe_dump(accept_play))
    subprocess.run(['ansible-playbook', '-i', 'localhost,', str(p)], check=True)
print('PASS: install_aap accepts unlicensed gateway after controller-route wait')
if 'Create organizations directly' in apply_aap:
    raise SystemExit(
        'FAIL: do not PATCH existing Controller orgs with '
        'Create organizations directly (AAP 2.5+ 400)'
    )
if 'ensure_controller_organization.yml' not in apply_aap:
    raise SystemExit('FAIL: AAP 2.5+ apply must ensure orgs without updating')
if 'Ensure organizations exist without updating' not in apply_aap:
    raise SystemExit('FAIL: AAP 2.5+ apply missing lookup-first org ensure')
ensure_org = (
    ROOT / 'roles/bootstrap_controller/tasks/ensure_controller_organization.yml'
).read_text()
if 'Look up existing org' not in ensure_org:
    raise SystemExit('FAIL: org ensure must lookup before create')
if 'Create when missing' not in ensure_org:
    raise SystemExit('FAIL: org ensure must create only when missing')
create_block = ensure_org.split('Ensure organization | Create when missing', 1)[-1]
create_task = create_block.split('- name:', 1)[0]
if 'description:' in create_task:
    raise SystemExit('FAIL: org create must not send description (PATCH 400)')
env_defaults = read('roles/bootstrap_generate_env_vars/defaults/main.yml')
ui_apps = env_defaults.get('bootstrap_generate_env_vars_preflight_ui_openshift_apps') or []
non_ui = env_defaults.get('bootstrap_generate_env_vars_non_ui_openshift_playbook_apps') or []
if 'ocp_compliance' not in ui_apps:
    raise SystemExit('FAIL: ocp_compliance must stay in the preflight OpenShift catalog')
if 'ocp_compliance' in non_ui:
    raise SystemExit('FAIL: ocp_compliance must not be treated as a leftover non-UI app')
print('PASS: existing Controller org is left unchanged; ocp_compliance stays a UI app')
