"""Test generated selection, workflow ordering and CLI execution without a cluster."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

root = Path(__file__).resolve().parents[3]
role = root / 'roles/bootstrap_generate_playbook_repo'
spec = importlib.util.spec_from_file_location('runner', role / 'files/local_components.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
catalogue = yaml.safe_load((role / 'defaults/main.yml').read_text())['bootstrap_generate_playbook_repo_generated_playbooks']
selected = [entry for entry in catalogue if entry['app'] in ['rhbk', 'rhbk_realm', 'rhbk_client']]
with tempfile.TemporaryDirectory(prefix='ado-local-components-') as directory:
    repo = Path(directory)
    for entry in selected:
        dest = repo / entry['dest']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(role / 'files' / entry['dest'], dest)
    plan = runner.build(repo, selected, root / 'roles/bootstrap_controller', 'example')
    paths = [step['id'] for step in plan['steps']]
    install = 'playbooks/rhbk/ado-deploy-and-configure-bootstrap.yml'
    realm = 'playbooks/rhbk/ado-manage-realm-bootstrap.yml'
    client = 'playbooks/rhbk/ado-manage-client-bootstrap.yml'
    enable = 'playbooks/rhbk/ado-enable-realm-bootstrap.yml'
    assert paths.index(install) < paths.index(realm) < paths.index(client)
    assert not any('pre_tasks' in path for path in paths)
    assert not any('grafana' in path for path in paths)
    enable_steps = [step for step in plan['steps'] if step['id'] == enable]
    assert enable_steps and enable_steps[0]['recommended'] is False
    # Nested OpenShift workflow: OAuth must follow Deploy RHBK when both selected.
    oauth_cat = [
        entry for entry in catalogue
        if entry['dest'] in (
            install,
            'playbooks/openshift/ado-configure-oauth-with-rhbk-bootstrap.yml',
            'playbooks/openshift/ado-configure-ldap-auth-bootstrap.yml',
            'playbooks/openshift/ado-create-htpass-user-bootstrap.yml',
        )
    ]
    oauth_repo = Path(tempfile.mkdtemp(prefix='ado-oauth-order-'))
    try:
        for entry in oauth_cat:
            dest = oauth_repo / entry['dest']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(role / 'files' / entry['dest'], dest)
        oauth_plan = runner.build(
            oauth_repo, oauth_cat, root / 'roles/bootstrap_controller', 'example'
        )
        oauth = 'playbooks/openshift/ado-configure-oauth-with-rhbk-bootstrap.yml'
        ldap = 'playbooks/openshift/ado-configure-ldap-auth-bootstrap.yml'
        oauth_paths = [step['id'] for step in oauth_plan['steps']]
        assert oauth_paths.index(install) < oauth_paths.index(oauth)
        # Selection order can prefer LDAP first; hard edge still puts Deploy
        # RHBK before OAuth.
        (oauth_repo / 'component-run-plan.json').write_text(json.dumps(oauth_plan))
        wanted = [oauth, ldap, install]
        cmds = runner.commands(oauth_repo, oauth_plan, {'steps': wanted})
        assert [step['id'] for step, _ in cmds] == [ldap, install, oauth]
    finally:
        shutil.rmtree(oauth_repo, ignore_errors=True)
    (repo / 'component-run-plan.json').write_text(json.dumps(plan))
    request = {'steps': [realm, install], 'extra_args': '-e "message=hello world" --check'}
    commands = runner.commands(repo, plan, request)
    assert [step['id'] for step, _ in commands] == [install, realm]
    assert commands[0][1][-3:] == ['-e', 'message=hello world', '--check']
    extra = json.loads(commands[0][1][5])
    assert extra['env'] == 'example'
    # Local runs must not force state=present; group_vars own delete/update.
    assert 'state' not in extra
    # Per-playbook step_options: typed vars merge into JSON -e; state/extra_args append.
    step_req = {
        'steps': [install],
        'extra_args': '-e state=present',
        'step_options': {
            install: {
                'state': 'absent',
                'vars': {'operator_channel': 'release-2.17'},
                'extra_args': '-e custom_flag=1',
            }
        },
    }
    step_cmds = runner.commands(repo, plan, step_req)
    step_argv = step_cmds[0][1]
    step_extra = json.loads(step_argv[5])
    assert step_extra['operator_channel'] == 'release-2.17'
    assert 'state=absent' in step_argv
    assert 'custom_flag=1' in step_argv
    assert step_argv.index('state=absent') > step_argv.index('state=present')
    for bad in [[], ['../../outside.yml'], [install, install]]:
        try:
            runner.commands(repo, plan, {'steps': bad})
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid selection accepted')
    # Real CLI calls a controlled executable; prove order and stop-on-failure.
    executable = repo / 'bin/ansible-playbook'
    executable.parent.mkdir()
    executable.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nwith Path(os.environ["CALLS"]).open("a") as f:f.write(sys.argv[3]+"\\n")\nsys.exit(int(os.environ.get("FAIL_CODE","0")))\n')
    executable.chmod(0o755)
    request_path = repo / 'request.json'
    request_path.write_text(json.dumps(request))
    calls = repo / 'calls'
    env = dict(os.environ, PATH=str(executable.parent) + os.pathsep + os.environ['PATH'], CALLS=str(calls))
    argv = ['python3', str(role / 'files/local_components.py'), '--repo', str(repo), '--request', str(request_path)]
    subprocess.run(argv, env=env, check=True)
    assert calls.read_text().splitlines() == [install, realm]
    calls.write_text('')
    result = subprocess.run(argv, env=dict(env, FAIL_CODE='9'), check=False)
    assert calls.read_text().splitlines() == [install]
    # Ingress-only selection must not surface IdM ACME / AWSPCA playbooks.
    cert = [entry for entry in catalogue if entry['app'] == 'cert_manager']
    ingress_only = runner.filter_cert_manager(cert, mode='cert', update_default_ingress=True)
    dests = {entry['dest'] for entry in ingress_only}
    assert 'playbooks/cert-manager/ado-deploy-and-configure-bootstrap.yml' in dests
    assert 'playbooks/cert-manager/ado-update-default-ingress-cert-bootstrap.yml' in dests
    assert 'playbooks/cert-manager/ado-configure-idm-acme-clusterissuer.yml' not in dests
    assert 'playbooks/cert-manager/ado-install-and-configure-awspca-bootstrap.yml' not in dests
    assert 'playbooks/cert-manager/configure-idm-acme-clusterissuer-tasks.yml' in dests
    assert 'playbooks/cert-manager/uninstall-cert-manager-tasks.yml' in dests
    acme = runner.filter_cert_manager(cert, mode='idm_acme', update_default_ingress=False)
    acme_dests = {entry['dest'] for entry in acme}
    assert 'playbooks/cert-manager/ado-configure-idm-acme-clusterissuer.yml' in acme_dests
    assert 'playbooks/cert-manager/configure-idm-acme-clusterissuer-tasks.yml' in acme_dests
    assert 'playbooks/cert-manager/ado-update-default-ingress-cert-bootstrap.yml' not in acme_dests
    # Task helpers must not become runnable plan steps.
    cert_repo = Path(tempfile.mkdtemp(prefix='ado-cert-local-'))
    try:
        for entry in acme:
            dest = cert_repo / entry['dest']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(role / 'files' / entry['dest'], dest)
        cert_plan = runner.build(
            cert_repo, acme, root / 'roles/bootstrap_controller', 'example'
        )
        cert_paths = [step['id'] for step in cert_plan['steps']]
        assert 'playbooks/cert-manager/configure-idm-acme-clusterissuer-tasks.yml' not in cert_paths
        assert 'playbooks/cert-manager/ado-deploy-and-configure-bootstrap.yml' in cert_paths
    finally:
        shutil.rmtree(cert_repo, ignore_errors=True)
    print('PASS: selected steps only, workflow ordering, quoted options, invalid selection, fail-fast CLI, cert_manager gates')
