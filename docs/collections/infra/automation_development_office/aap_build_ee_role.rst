.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/roles/aap_build_ee/meta/argument_specs.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.aap_build_ee_role:

.. Title

infra.automation_development_office.aap_build_ee role -- Build a custom Ansible execution environment image.
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This role is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.aap_build_ee`.

.. contents::
   :local:
   :depth: 2

.. _ansible_collections.infra.automation_development_office.aap_build_ee_role__entrypoint-main:

.. Entry point title

Entry point ``main`` -- Build a custom Ansible execution environment image.
---------------------------------------------------------------------------

.. version_added


.. Deprecated


Synopsis
^^^^^^^^

.. Description

- This role builds an Ansible execution environment (EE) image from a caller\-selected
  base EE image and caller\-provided collection requirements.

.. Requirements


.. Options

Parameters
^^^^^^^^^^

.. tabularcolumns:: \X{1}{3}\X{2}{3}

.. list-table::
  :width: 100%
  :widths: auto
  :header-rows: 1
  :class: longtable ansible-option-table

  * - Parameter
    - Comments

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_ansible_core"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_ansible_core:

      .. rst-class:: ansible-option-title

      **aap_build_ee_ansible_core**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_ansible_core" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Optional ansible\-core pip spec rendered to dependencies.ansible\_core.package\_pip. Accepts a version shorthand (for example "2.16") or any pip\-compatible value (for example ansible\-core==2.16.0). Required for minimal base images that do not include Ansible.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`""`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_ansible_runner"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_ansible_runner:

      .. rst-class:: ansible-option-title

      **aap_build_ee_ansible_runner**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_ansible_runner" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Optional ansible\-runner pip spec rendered to dependencies.ansible\_runner.package\_pip. Accepts a version shorthand (for example "2.4") or any pip\-compatible value. Required for minimal base images that do not include Ansible Runner.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`""`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_base_ee"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_base_ee:

      .. rst-class:: ansible-option-title

      **aap_build_ee_base_ee**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_base_ee" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Base EE image name and tag, for example ee\-minimal\-rhel9:latest.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_build_context"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_build_context:

      .. rst-class:: ansible-option-title

      **aap_build_ee_build_context**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_build_context" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Directory path used as ansible\-builder context.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"/tmp/aap\_build\_ee"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_builder_executable"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_builder_executable:

      .. rst-class:: ansible-option-title

      **aap_build_ee_builder_executable**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_builder_executable" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      ansible\-builder executable name or full path.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"ansible\-builder"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_collection_files"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_collection_files:

      .. rst-class:: ansible-option-title

      **aap_build_ee_collection_files**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_collection_files" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      List of local collection artifact paths (\*.tar.gz) to include in the built EE image.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_collections"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_collections:

      .. rst-class:: ansible-option-title

      **aap_build_ee_collections**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_collections" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`any`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Collection requirements input. Accepts a dict keyed by collection name (for example redhat.satellite: "5.11.0"), a list of name/version objects, or a single flat object with name and version keys.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`{}`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_output_image"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_output_image:

      .. rst-class:: ansible-option-title

      **aap_build_ee_output_image**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_output_image" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Target image name and tag for the built EE image.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`"custom\-ee:latest"`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_package_manager_path"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_package_manager_path:

      .. rst-class:: ansible-option-title

      **aap_build_ee_package_manager_path**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_package_manager_path" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Optional package manager executable path override used by ansible\-builder in the base image. When empty, ansible\-builder uses its own default.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`""`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-main--aap_build_ee_source_image_repository"></div>

      .. _ansible_collections.infra.automation_development_office.aap_build_ee_role__parameter-main__aap_build_ee_source_image_repository:

      .. rst-class:: ansible-option-title

      **aap_build_ee_source_image_repository**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-main--aap_build_ee_source_image_repository" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Source container repository path used to pull the base EE image.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso





.. Extra links

Collection links
~~~~~~~~~~~~~~~~

.. ansible-links::

  - title: "Issue Tracker"
    url: "https://github.com/redhat-cop/infra.automation-development-office/issues"
    external: true
  - title: "Repository (Sources)"
    url: "https://github.com/redhat-cop/infra.automation-development-office"
    external: true
  - title: "Report an issue"
    url: "https://github.com/ansible-collections/infra.automation_development_office/issues/new/choose"
    external: true


.. Parsing errors
