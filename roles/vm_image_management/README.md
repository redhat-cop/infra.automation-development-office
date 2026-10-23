# Role: infra.automation_development_office.vm_image_management

This Ansible role creates a qcow2 virtual machine image from an existing base image.

In its current form, the role runs prerequisite setup, validates the source and destination paths, expands the base and destination paths from directory and file name components, inspects the base image with `qemu-img info`, and creates the output image with `qemu-img convert`.

> **⚠️ Note:**
> This role expects `qemu-img` to be installed on the target host. The base image must already exist on the managed host for the active create workflow.

## Role Author

Automation Development Office

## ✅ Role Requirements

- Ansible >= 2.9
- Target hosts reachable by Ansible.
- `qemu-img` must be installed on the managed host.
- The destination storage location must have enough free space for the converted image.

## 📦 Role Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `vm_image_management_action` | Action selector used by the prerequisite and assertion tasks. The active workflow expects `create`. | ✅ | Not set in defaults |
| `vm_image_management_dest_path` | Destination path input. In prerequisites, this is expanded to the final output image path by appending `vm_image_management_dest_name`. | ✅ | Not set in defaults |
| `vm_image_management_dest_name` | Output image file name appended to `vm_image_management_dest_path` in prerequisites. | ✅ | Not set in defaults |
| `vm_image_management_base_path` | Base image directory input. In prerequisites, this is expanded to the final base image path by appending `vm_image_management_base_name`. | ✅ | Not set in defaults |
| `vm_image_management_base_name` | Base image file name appended to `vm_image_management_base_path` in prerequisites. | ✅ | Not set in defaults |
| `vm_image_management_format` | Output image format passed to `qemu-img convert -O`. | ❌ | `qcow2` |
| `vm_image_management_download` | When `false`, the current create workflow runs. Download flow remains present but commented out in `main.yml`. | ❌ | `false` |
| `vm_image_management_path` | Reserved default variable for a full destination path. It is defined in defaults but is not used by the current task flow. | ❌ | `null` |
| `vm_image_management_size` | Reserved for future image sizing workflows. Not used by the current task flow. | ❌ | `null` |
| `vm_image_management_force` | Reserved for future replacement behavior. Not used by the current task flow. | ❌ | `false` |
| `vm_image_management_resize` | Reserved for a future post-create resize workflow. `main.yml` currently includes a TODO for this feature. | ❌ | `false` |
| `vm_image_management_backing` | Legacy variable from the earlier workflow. Not used by the current task flow. | ❌ | `true` |

> **Notes:**
> The role currently expands both source and destination paths inside `pre_reqs.yml`.
> `vm_image_management_action` is required by the current task guards even though it is not defined in `defaults/main.yml`.
> The expanded `vm_image_management_dest_path` becomes the final output file path used by the create task.
> Several variables still exist in `defaults/main.yml`, but only a subset is used by the current implementation.

See `defaults/main.yml` for the current defaulted variable set.

## 🚀 Role Usage

Define the base image directory and file name, then define the destination directory, output image file name, and `vm_image_management_action`.

### Example 1: Create a qcow2 image from a local base image
```yaml
- hosts: hypervisors
  become: true
  vars:
    vm_image_management_dest_path: /var/lib/libvirt/images
    vm_image_management_dest_name: rhel9-app01.qcow2
    vm_image_management_base_path: /var/lib/libvirt/images
    vm_image_management_base_name: rhel9-base.qcow2
    vm_image_management_action: create
    vm_image_management_format: qcow2
    vm_image_management_download: false
  roles:
    - role: infra.automation_development_office.vm_image_management
```

### Example 2: Create a raw image from the same base image
```yaml
- hosts: hypervisors
  become: true
  vars:
    vm_image_management_dest_path: /var/lib/libvirt/images
    vm_image_management_dest_name: rhel9-app01.img
    vm_image_management_base_path: /var/lib/libvirt/images
    vm_image_management_base_name: rhel9-base.qcow2
    vm_image_management_action: create
    vm_image_management_format: raw
    vm_image_management_download: false
  roles:
    - role: infra.automation_development_office.vm_image_management
```

## 🔧 Tasks Overview

- **Main Task File** (`main.yml`):
  - Imports prerequisite tasks before image creation.
  - Imports the image creation workflow when `vm_image_management_download` is `false`.
  - Includes a TODO note for a future resize workflow controlled by `vm_image_management_resize`.
  - Contains commented placeholder logic for a future download workflow.
- **Prerequisites** (`pre_reqs.yml`):
  - Expands `vm_image_management_dest_path` by appending `vm_image_management_dest_name`.
  - Builds the effective base image path by appending `vm_image_management_base_name` to `vm_image_management_base_path`.
  - Runs only when `vm_image_management_action == "create"` and `vm_image_management_download` is `false`.
  - Imports the assertion tasks.
- **Assertions** (`assertions.yml`):
  - Verifies that the expanded base image path is not blank.
  - Verifies that the expanded destination image path is not blank.
  - Emits success messages describing the selected base image and destination image path.
  - Runs only when `vm_image_management_action == "create"` and `vm_image_management_download` is `false`.
- **Create Qcow From Base** (`create_qcow_from_base.yml`):
  - Runs `qemu-img info --output=json` against the base image.
  - Parses the reported backing format into a fact.
  - Uses `qemu-img convert` to create the destination image at the expanded `vm_image_management_dest_path` in the requested format.
- **Download Base Image** (`download_base_image.yml`):
  - Provides a `get_url` task for downloading a base image.
  - Exists in the role, but is not currently imported by `main.yml`.

## 🧪 Role Molecule Testing

This role includes a role-local Molecule scenario under `molecule/default/` and an extension-level integration scenario under `extensions/molecule/integration_vm_image_management` used by CI.

The scenario:

- Creates a temporary base image under `/tmp/vm_image_management_molecule`
- Runs the role with `vm_image_management_action: create`
- Verifies that the cloned image exists and reports `qcow2` format
- Removes the temporary test artifacts during `destroy`

### Run the scenario

Run the role-local scenario from the role directory:

```bash
cd roles/vm_image_management
python -m molecule test -s default
```

Run the extension-level CI-aligned scenario from the collection root:

```bash
cd /path/to/your/git/checkout/infra.automation_development_office
ansible-galaxy collection install . --force -p ~/.ansible/collections
ansible-galaxy collection install ansible.posix --force -p ~/.ansible/collections
export ANSIBLE_COLLECTIONS_PATH="$HOME/.ansible/collections:/usr/share/ansible/collections"
cd extensions
molecule test -s integration_vm_image_management
```

For fish shell:

```fish
set -gx ANSIBLE_COLLECTIONS_PATH "$HOME/.ansible/collections:/usr/share/ansible/collections"
```

### GitHub Actions manual runs

The `Ansible Collection CI/CD` workflow exposes the vm_image_management integration scenario as a checkbox in `workflow_dispatch`.

- Checked scenarios are included in the Molecule matrix.
- Matrix jobs run in parallel.

## 📁 Role Structure

```
vm_image_management/
├── defaults/
│   └── main.yml
├── molecule/
│   └── default/
│       ├── converge.yml
│       ├── destroy.yml
│       ├── molecule.yml
│       ├── README.md
│       └── verify.yml
├── tasks/
│   ├── assertions.yml
│   ├── create_qcow_from_base.yml
│   ├── download_base_image.yml
│   ├── main.yml
│   └── pre_reqs.yml
└── README.md
```
