# Role: ado.aap_build_ee

Build a custom Ansible **Execution Environment (EE)** image with `ansible-builder`.

- Uses a caller-provided base EE image
- Pulls the base image from a caller-provided source repository
- Adds caller-provided Galaxy collections and/or local collection artifacts during the EE build

---

## Role Author

- Automation Development Office

---

## ✅ Role Requirements

- Ansible >= 2.14
- `ansible-builder` available on the managed host where the role runs
- Container runtime dependencies required by `ansible-builder`

---

## 📦 Role Variables

| Variable | Description |
| -------- | ----------- |
| `aap_build_ee_base_ee` | Base EE image name and tag (for example `ee-minimal-rhel9:latest`). **Required.** |
| `aap_build_ee_source_image_repository` | Source image repository path used with the base EE image name (for example `registry.redhat.io/ansible-automation-platform-24`). **Required.** |
| `aap_build_ee_collections` | Collection requirements for generated `requirements.yml`. Accepts a dict keyed by collection name (for example `redhat.satellite: "5.11.0"`), a list of `name`/`version` objects, or a single flat object with `name` and `version` keys. Use `""` for no version pin. Default: `{}`. |
| `aap_build_ee_collection_files` | List of local built collection artifact files (`*.tar.gz`). The role copies them into build context and installs them with `type: file`. Default: `[]`. |
| `aap_build_ee_output_image` | Output image name and tag for the built EE. Default: `custom-ee:latest`. |
| `aap_build_ee_build_context` | Build context directory used by `ansible-builder`. Default: `/tmp/aap_build_ee`. |
| `aap_build_ee_builder_executable` | `ansible-builder` executable name or full path. Default: `ansible-builder`. |
| `aap_build_ee_package_manager_path` | Optional package manager path override used by `ansible-builder` (for example `/usr/bin/microdnf` or `/usr/bin/dnf`). Leave empty to use ansible-builder defaults. Default: `""`. |
| `aap_build_ee_ansible_core` | Optional ansible-core pip spec for `dependencies.ansible_core.package_pip`. Accepts a version shorthand (for example `"2.16"` renders as `ansible-core==2.16`) or any pip-compatible value (for example `ansible-core==2.16.0`, `>=2.16,<2.17`). Required for minimal base images without preinstalled Ansible. Default: `""`. |
| `aap_build_ee_ansible_runner` | Optional ansible-runner pip spec for `dependencies.ansible_runner.package_pip`. Accepts a version shorthand (for example `"2.4"` renders as `ansible-runner==2.4`) or any pip-compatible value. Required for minimal base images without preinstalled Ansible Runner. Default: `""`. |

### Auth via environment (optional)

No role-specific environment authentication variables are required by this role.

At least one of `aap_build_ee_collections` or
`aap_build_ee_collection_files` must be non-empty.

---

## 🚀 Role Usage

### Build a custom EE image

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          ansible.posix: ""
          community.general: ""
        aap_build_ee_output_image: localhost/custom-ee:latest
```

### Build with a custom context directory

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-supported-rhel9:latest
        aap_build_ee_source_image_repository: quay.io/ansible
        aap_build_ee_collections:
          community.general: ""
        aap_build_ee_build_context: /tmp/ee-build-demo
        aap_build_ee_output_image: localhost/custom-ee:demo
```

### Build with pinned collection versions

Dict keyed by collection name:

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          ansible.posix: "1.5.4"
          community.general: ">=9.0.0,<11.0.0"
        aap_build_ee_output_image: localhost/custom-ee:versioned
```

List of name/version objects (matches ansible-builder requirements structure):

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          - name: redhat.satellite
            version: "5.11.0"
        aap_build_ee_output_image: localhost/custom-ee:versioned
```

Single flat object (single collection convenience):

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          name: redhat.satellite
          version: "5.11.0"
        aap_build_ee_output_image: localhost/custom-ee:versioned
```

### Build with explicit package manager override (minimal base image)

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          ansible.posix: ""
        aap_build_ee_package_manager_path: /usr/bin/microdnf
        aap_build_ee_ansible_core: "2.16"
        aap_build_ee_ansible_runner: "2.4"
        aap_build_ee_output_image: localhost/custom-ee:minimal
```

### Build using a local collection artifact

```yaml
- hosts: localhost
  gather_facts: false
  roles:
    - role: infra.automation_development_office.aap_build_ee
      vars:
        aap_build_ee_base_ee: ee-minimal-rhel9:latest
        aap_build_ee_source_image_repository: registry.redhat.io/ansible-automation-platform-24
        aap_build_ee_collections:
          ansible.posix: ""
        aap_build_ee_collection_files:
          - /tmp/builds/infra-automation_development_office-0.1.0.tar.gz
        aap_build_ee_output_image: localhost/custom-ee:with-local
```

---

### Behavior Notes

- The role composes the base image reference from repository + base EE image.
- It renders `execution-environment.yml` and `requirements.yml` into the build context.
- It normalizes `aap_build_ee_collections` from dict, list, or flat object input into
  a canonical list before rendering `requirements.yml`.
- It runs `ansible-builder build` using the rendered files and selected output tag.
- It validates local artifact paths from `aap_build_ee_collection_files` before build.
- It injects local collection artifacts via `additional_build_files` into `collection-artifacts/` inside `_build`.
- It sets `options.package_manager_path` in the EE definition only when
  `aap_build_ee_package_manager_path` is explicitly provided.
- It sets `dependencies.ansible_core.package_pip` and `dependencies.ansible_runner.package_pip`
  only when the corresponding role variables are explicitly provided.
- Required inputs are enforced by role argument specs and runtime assertions.

---

## 🧪 Role Molecule Testing

Use the extension integration scenario at
`extensions/molecule/integration_aap_build_ee`.

Install collection and dependencies before running locally:

```bash
cd /path/to/your/git/checkout/infra.automation_development_office
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix --force -p ~/.ansible/collections
ansible-galaxy collection install community.general --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
```

Run integration scenario locally:

```bash
cd extensions
molecule test -s integration_aap_build_ee
```

If your environment restricts writes under `~/.ansible/tmp`, set writable temp paths:

```bash
mkdir -p .ansible/tmp
export ANSIBLE_LOCAL_TEMP="$PWD/.ansible/tmp"
export ANSIBLE_REMOTE_TMP="$PWD/.ansible/tmp"
```

---

## 📁 Role Structure

```text
roles/
└─ aap_build_ee/
   ├─ README.md
   ├─ defaults/
   │  └─ main.yml
   ├─ meta/
   │  ├─ main.yml
   │  └─ argument_specs.yml
   ├─ tasks/
   │  └─ main.yml
   └─ templates/
      ├─ execution-environment.yml.j2
      └─ requirements.yml.j2
```
