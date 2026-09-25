"""Build and execute the generated local component plan (no Controller needed)."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

import yaml


def load(path):
    return yaml.safe_load(path.read_text()) or {}


def filter_cert_manager(catalogue, mode='cert', update_default_ingress=False):
    """Keep cert_manager playbooks aligned with Contoller mode/ingress gates."""
    mode = (mode or 'cert').strip() or 'cert'
    ingress = bool(update_default_ingress)
    kept = []
    for item in catalogue:
        dest = item.get('dest') or ''
        if dest.endswith('ado-configure-idm-acme-clusterissuer.yml') and mode != 'idm_acme':
            continue
        if dest.endswith('ado-install-and-configure-awspca-bootstrap.yml') and mode != 'aws_pca':
            continue
        if dest.endswith('ado-update-default-ingress-cert-bootstrap.yml') and not ingress:
            continue
        kept.append(item)
    return kept


def _workflow_playbooks(jt_name, names, workflows_by_name, seen=None):
    """Expand a JT or nested workflow name to concrete playbook paths."""
    seen = seen if seen is not None else set()
    if not jt_name or jt_name in seen:
        return set()
    if jt_name in names:
        return {names[jt_name]}
    workflow = workflows_by_name.get(jt_name)
    if not workflow:
        return set()
    seen = set(seen)
    seen.add(jt_name)
    playbooks = set()
    for node in workflow.get('simplified_workflow_nodes') or []:
        playbooks |= _workflow_playbooks(
            node.get('unified_job_template'), names, workflows_by_name, seen
        )
    return playbooks


def build_edges(controller):
    """Playbook dependency edges from Contoller workflow success_nodes.

    Nested workflow nodes (e.g. ``ADO | RHBK Workflow`` → OAuth) expand to the
    playbooks inside that nested workflow so local runs match Contoller order.
    """
    names = {}
    for file in sorted((controller / 'files/job_templates').glob('*.yml')):
        for item in load(file).get('controller_templates', []):
            path = item.get('playbook')
            if path and item.get('name'):
                names[item['name']] = path

    workflows_by_name = {}
    for file in sorted((controller / 'files/workflows').glob('*.yml')):
        for workflow in load(file).get('controller_workflow_job_templates', []):
            name = workflow.get('name')
            if name:
                workflows_by_name[name] = workflow

    edges = {}
    for workflow in workflows_by_name.values():
        nodes = workflow.get('simplified_workflow_nodes') or []
        id_to_jt = {
            node.get('identifier'): node.get('unified_job_template')
            for node in nodes
            if node.get('identifier')
        }
        for node in nodes:
            sources = _workflow_playbooks(
                node.get('unified_job_template'), names, workflows_by_name
            )
            for target_id in node.get('success_nodes') or []:
                targets = _workflow_playbooks(
                    id_to_jt.get(target_id), names, workflows_by_name
                )
                for source in sources:
                    for destination in targets:
                        if source and destination and source != destination:
                            edges.setdefault(destination, set()).add(source)
    return edges, names


def is_day2_helper(path, title=''):
    """One-shot helpers that should not be auto-selected with full RHBK install."""
    blob = f'{path} {title}'.lower()
    return 'enable-realm' in blob


def build(repo, catalogue, controller, environment):
    edges, _names = build_edges(controller)
    templates = {}
    for file in sorted((controller / 'files/job_templates').glob('*.yml')):
        for item in load(file).get('controller_templates', []):
            path = item.get('playbook')
            if path:
                templates.setdefault(path, item)

    steps = []
    for item in catalogue:
        path = item['dest']
        source = repo / path
        if not source.resolve().is_relative_to(repo.resolve()):
            raise ValueError('Playbook outside generated repository')
        plays = load(source)
        # Supporting task files are generated too, but must never be executed.
        if not isinstance(plays, list) or not all(
            isinstance(p, dict) and ('hosts' in p or 'import_playbook' in p)
            for p in plays
        ):
            continue
        template = templates.get(path, {})
        # Local / no-AAP runs already have form intent in generated group_vars.
        # Do not re-surface Contoller survey fields (that felt like a second form).
        fields = []
        extra = template.get('extra_vars') or {}
        if isinstance(extra, str):
            extra = yaml.safe_load(extra) or {}
        # Drop Contoller-templated extras; env/state are set at execute time.
        extra = {
            key: value for key, value in (extra.items() if isinstance(extra, dict) else [])
            if '{{' not in str(value) and key not in ('env', 'state')
        }
        unsupported = False
        title = template.get('name') or plays[0].get('name', path)
        destructive = any(
            word in (title + ' ' + path).lower()
            for word in ('delete', 'remove', 'reset', 'uninstall')
        )
        recommended = (
            not destructive
            and not unsupported
            and not is_day2_helper(path, title)
        )
        steps.append({
            'id': path,
            'playbook': path,
            'component': item['app'],
            'title': title,
            'recommended': recommended,
            'fields': fields,
            'extra_vars': extra,
            'available': not unsupported,
            'reason': (
                'Day-2 helper (realm already created/enabled by Deploy RHBK / '
                'Deploy RHBK Realm). Select only when fixing a disabled realm.'
                if is_day2_helper(path, title) else ''
            ),
            'depends_on': sorted(edges.get(path, set())),
        })

    # Topological order from workflow edges; catalog order breaks ties.
    remaining = list(steps)
    ordered = []
    while remaining:
        pending = {s['id'] for s in remaining}
        ready = [
            s for s in remaining
            if not (edges.get(s['id'], set()) & pending)
        ]
        if not ready:
            raise ValueError('Selected workflow ordering contains a cycle')
        # Stable: first ready step in current remaining (catalog) order.
        pick = ready[0]
        ordered.append(pick)
        remaining.remove(pick)
    return {
        'version': 1,
        'environment': environment,
        'steps': ordered,
        'edges': {key: sorted(value) for key, value in sorted(edges.items())},
    }


def order_selected(selected, by_id, edges):
    """Order selected steps by workflow deps; preserve selection order on ties.

    Selection order is adjustable in the UI for independent steps (e.g. LDAP vs
    HTPasswd). Hard Contoller edges still win (Deploy RHBK before OAuth).
    """
    selected_set = set(selected)
    priority = {step_id: index for index, step_id in enumerate(selected)}
    remaining = [by_id[step_id] for step_id in selected]
    ordered = []
    while remaining:
        pending = {step['id'] for step in remaining}
        ready = [
            step for step in remaining
            if not (edges.get(step['id'], set()) & pending)
        ]
        if not ready:
            raise ValueError(
                'Selected component order has a dependency cycle. '
                'Clear selection and use recommended workflow order.'
            )
        ready.sort(key=lambda step: priority.get(step['id'], 10**6))
        pick = ready[0]
        ordered.append(pick)
        remaining.remove(pick)
    # If selection order already violated a hard edge, surface a short note via
    # stderr only when order changed — callers may ignore.
    if [step['id'] for step in ordered] != list(selected):
        print(
            'Note: adjusted run order to match Contoller workflow dependencies '
            f'(wanted {[by_id[s]["title"] for s in selected]}, '
            f'running {[s["title"] for s in ordered]}).',
            file=sys.stderr,
        )
    return ordered


def is_htpasswd_playbook(step):
    """Only Admin HTPasswd playbooks should receive htpasswd_* form overrides."""
    path = str(step.get("playbook") or step.get("id") or "").lower()
    component = str(step.get("component") or "").lower()
    title = str(step.get("title") or "").lower()
    return any(
        token in path or token in component or token in title
        for token in ("htpass", "htpasswd", "admin_htpasswd")
    )


def commands(repo, plan, request):
    selected = request.get('steps', [])
    if not isinstance(selected, list) or not selected:
        raise ValueError('Select at least one generated component step')
    by_id = {s['id']: s for s in plan['steps']}
    if len(selected) != len(set(selected)) or any(s not in by_id for s in selected):
        raise ValueError('Selection contains duplicate or unknown playbooks')
    edges = {
        key: set(value)
        for key, value in (plan.get('edges') or {}).items()
    }
    # Rebuild edges from depends_on on steps when plan was generated before
    # edges were persisted.
    if not edges:
        for step in plan['steps']:
            deps = step.get('depends_on') or []
            if deps:
                edges[step['id']] = set(deps)
    ordered_steps = order_selected(selected, by_id, edges)
    extra = shlex.split(request.get('extra_args', ''))
    result = []
    for step in ordered_steps:
        if not step['available']:
            raise ValueError(step['reason'])
        playbook = (repo / step['playbook']).resolve()
        if not playbook.is_relative_to(repo.resolve()) or not playbook.is_file():
            raise ValueError('Generated playbook is missing or outside the repository')
        # Local / no-AAP: form+bootstrap already wrote group_vars/vault (including
        # component state such as console banner delete). Do not put state in -e —
        # that would override vars_files absent/delete. Roles must use
        # state|default('present'). Pass ``-e state=absent`` in additional options
        # when you need an explicit CLI delete (appended after this JSON -e).
        values = dict(step.get("extra_vars", {}), env=plan["environment"])
        values.pop("state", None)
        step_opts = (request.get("step_options") or {}).get(step["id"]) or {}
        if not isinstance(step_opts, dict):
            step_opts = {}
        # Per-playbook typed overrides (channel, etc.) merge into the JSON -e blob.
        for key, value in (step_opts.get("vars") or {}).items():
            if value is None or value == "":
                continue
            values[key] = value
        # htpasswd_* overrides are only for the HTPasswd playbook — never leak onto
        # cert-manager / other steps (preview used to show them on every command).
        if is_htpasswd_playbook(step):
            form_vars = request.get("form_vars") or {}
            if not isinstance(form_vars, dict):
                form_vars = {}
            allowed_form = {
                "htpasswd_idp_name",
                "htpasswd_idp",
                "htpasswd_secret",
                "htpasswd_action",
            }
            # Fall back to generated group_vars when the UI omitted IdP fields.
            if not str(form_vars.get("htpasswd_idp_name") or "").strip():
                env_name = str(plan.get("environment") or "dev")
                env_dir = repo / "group_vars" / "all" / env_name
                for name in (
                    "vars_admin_htpasswd.yml",
                    "vars_htpass_admin.yml",
                    "vars_openshift.yml",
                ):
                    path = env_dir / name
                    if not path.is_file():
                        continue
                    try:
                        data = load(path)
                    except (OSError, ValueError, yaml.YAMLError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    for key in allowed_form:
                        value = data.get(key)
                        if value not in (None, "") and key not in form_vars:
                            form_vars[key] = value
                    if str(form_vars.get("htpasswd_idp_name") or "").strip():
                        break
            for key, value in form_vars.items():
                if key in allowed_form and value not in (None, ""):
                    values[key] = value
        args = ["ansible-playbook", "-i", "inventory", step["playbook"], "-e", json.dumps(values)]
        if (repo / ".vault_pass").is_file():
            args += ["--vault-password-file", ".vault_pass"]
        # Global extra_args first (includes Common -e state=…), then per-step
        # overrides so playbook-specific state/channel/-e win.
        args += extra
        step_state = str(step_opts.get("state") or "").strip().lower()
        if step_state in ("present", "absent"):
            args += ["-e", f"state={step_state}"]
        step_extra = shlex.split(str(step_opts.get("extra_args") or ""))
        args += step_extra
        result.append((step, args))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--build', type=Path, help='Selected playbook catalog JSON')
    parser.add_argument('--controller-role', type=Path)
    parser.add_argument('--environment')
    parser.add_argument('--request', type=Path, help='Selected steps, values and extra_args JSON')
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve()
    if args.build:
        plan = build(repo, json.loads(args.build.read_text()), args.controller_role, args.environment)
        target = repo / 'component-run-plan.json'
        content = json.dumps(plan, indent=2) + '\n'
        if not target.exists() or target.read_text() != content:
            target.write_text(content)
            print('updated')
        return
    plan = json.loads((repo / 'component-run-plan.json').read_text())
    if args.request is None:
        parser.error('--request is required to preview or execute components')
    request = json.loads(args.request.read_text())
    runs = commands(repo, plan, request)  # Validate all steps before executing any.
    if args.preview:
        preview = [{'id': step['id'], 'argv': argv} for step, argv in runs]
        print(json.dumps(preview))
        return
    for step, argv in runs:
        print('\n=== ' + step['title'] + ' ===', flush=True)
        result = subprocess.run(argv, cwd=repo, check=False)
        if result.returncode:
            sys.exit(result.returncode)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
