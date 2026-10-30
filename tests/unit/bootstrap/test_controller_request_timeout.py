"""Inventory apply must not keep the ansible.controller 10s read timeout."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
APPLY = REPO / "roles/bootstrap_controller/tasks/apply_aap_25_plus.yml"
DEFAULTS = REPO / "roles/bootstrap_controller/defaults/main.yml"
AAP = REPO / "roles/bootstrap_controller/tasks/aap.yml"


def test_inventory_create_sets_request_timeout() -> None:
    text = APPLY.read_text()
    inventory = text.split("Create inventories directly", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_inventory.yml" in inventory
    task = (REPO / "roles/bootstrap_controller/tasks/ensure_controller_inventory.yml").read_text()
    assert "ansible.controller.inventory:" in task
    assert "request_timeout:" in task
    assert "bootstrap_controller_request_timeout" in task
    assert "retries:" in task
    assert "until: bootstrap_controller_inventory_result is succeeded" in task
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_inventory_retries: 4" in defaults
    assert "bootstrap_controller_inventory_retry_delay: 10" in defaults


def test_org_lookup_retries_gateway_timeout() -> None:
    task = (
        REPO / "roles/bootstrap_controller/tasks/ensure_controller_organization.yml"
    ).read_text()
    status_line = task.split("status_code:", 1)[1].split("\n", 1)[0]
    assert "504" in status_line
    assert "bootstrap_controller_org_lookup_retries" in task
    assert "in [200, 401, 403, 404]" in task
    create = task.split("ansible.controller.organization:", 1)[1]
    assert "when:" in create
    assert "bootstrap_controller_ensure_org_lookup_ok" in create
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_org_lookup_retries: 4" in defaults
    assert "bootstrap_controller_org_lookup_retry_delay: 10" in defaults


def test_credential_create_retries_one_at_a_time() -> None:
    text = APPLY.read_text()
    credentials = text.split("Apply credentials", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_credential.yml" in credentials
    assert "include_role:" not in credentials
    task = (REPO / "roles/bootstrap_controller/tasks/ensure_controller_credential.yml").read_text()
    assert "include_tasks: apply_one_controller_credential.yml" in task
    assert "include_role:" not in task
    assert "bootstrap_controller_credential_ok: false" in task
    assert "range(" in task
    one = (REPO / "roles/bootstrap_controller/tasks/apply_one_controller_credential.yml").read_text()
    assert "infra.aap_configuration.dispatch" in one
    assert "controller_credentials: \"{{ [bootstrap_controller_credential] }}\"" in one
    assert "ansible.builtin.pause:" in one
    assert "delay:" not in one
    assert "retries:" not in one
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_credential_retries: 4" in defaults
    assert "bootstrap_controller_credential_retry_delay: 10" in defaults


def test_project_create_retries_one_at_a_time() -> None:
    sync = (
        REPO / "roles/bootstrap_controller/tasks/sync_controller_projects_before_templates.yml"
    ).read_text()
    apply = sync.split("Apply projects", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_project.yml" in apply
    assert "include_role:" not in apply
    task = (REPO / "roles/bootstrap_controller/tasks/ensure_controller_project.yml").read_text()
    assert "include_tasks: apply_one_controller_project.yml" in task
    assert "include_role:" not in task
    assert "bootstrap_controller_project_ok: false" in task
    assert "range(" in task
    one = (REPO / "roles/bootstrap_controller/tasks/apply_one_controller_project.yml").read_text()
    assert "infra.aap_configuration.controller_projects" in one
    assert 'controller_projects: "{{ [bootstrap_controller_project] }}"' in one
    assert "ansible.builtin.pause:" in one
    assert "delay:" not in one
    assert "retries:" not in one
    assert "retries:" in sync.split("Align existing project", 1)[1].split("- name:", 1)[0]
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_project_retries: 4" in defaults
    assert "bootstrap_controller_project_retry_delay: 10" in defaults


def test_host_and_group_create_retries_one_at_a_time() -> None:
    text = APPLY.read_text()
    hosts = text.split("Apply hosts", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_host.yml" in hosts
    assert "include_role:" not in hosts
    groups = text.split("Apply groups", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_group.yml" in groups
    assert "include_role:" not in groups
    host = (REPO / "roles/bootstrap_controller/tasks/ensure_controller_host.yml").read_text()
    one = (REPO / "roles/bootstrap_controller/tasks/apply_one_controller_host.yml").read_text()
    assert "bootstrap_controller_host_ok: false" in host
    assert "infra.aap_configuration.controller_hosts" in one
    assert 'controller_hosts: "{{ [bootstrap_controller_host] }}"' in one
    assert "ansible.builtin.pause:" in one
    assert "delay:" not in one
    group = (REPO / "roles/bootstrap_controller/tasks/apply_one_controller_group.yml").read_text()
    assert "infra.aap_configuration.controller_host_groups" in group
    assert 'controller_groups: "{{ [bootstrap_controller_group] }}"' in group
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_host_retries: 4" in defaults
    assert "bootstrap_controller_group_retries: 4" in defaults


def test_job_template_waits_for_the_api_call() -> None:
    text = APPLY.read_text()
    wait = text.split("Wait for job template API calls", 1)[1].split("- name:", 1)[0]
    assert "controller_configuration_job_templates_async_delay" in wait
    assert "bootstrap_controller_request_timeout" in wait
    apply = text.split("Apply job templates one at a time", 1)[1].split("- name:", 1)[0]
    assert "ensure_controller_job_template.yml" in apply
    assert "include_role:" not in apply
    one = (
        REPO / "roles/bootstrap_controller/tasks/apply_one_controller_job_template.yml"
    ).read_text()
    assert "infra.aap_configuration.controller_job_templates" in one
    assert 'controller_templates: "{{ [bootstrap_controller_job_template] }}"' in one
    assert "ansible.builtin.pause:" in one
    assert "delay:" not in one
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_job_template_async_delay: 5" in defaults
    assert "bootstrap_controller_job_template_retries: 4" in defaults


def test_request_timeout_default_is_above_module_default() -> None:
    defaults = DEFAULTS.read_text()
    assert "bootstrap_controller_request_timeout: 120" in defaults
    aap = AAP.read_text()
    assert "aap_request_timeout:" in aap
    assert "when: aap_request_timeout is not defined" in aap
    assert "noqa: var-naming[no-role-prefix]" in aap
