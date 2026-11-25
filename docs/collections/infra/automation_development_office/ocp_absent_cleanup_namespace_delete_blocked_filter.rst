.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/filter/ocp_absent_cleanup_namespace_delete_blocked.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked_filter:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked filter -- Return whether ocp\_namespace must refuse to delete a namespace
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This filter plugin is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked`.

.. version_added


.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- Return :literal:`true` when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_delete\_blocked#filter:name` is not a DNS\-1123 label.
- Return :literal:`true` for built\-in control\-plane namespaces, :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_delete\_blocked#filter:extra\_blocked`\ , and names that start with a blocked prefix.
- The default prefixes are :literal:`kube\-`. :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_delete\_blocked#filter:extra\_prefixes` are added to that list and cannot remove it.
- :literal:`openshift\-operators` is always blocked.
- Other component namespaces, such as :literal:`openshift\-gitops`\ , are not blocked unless named in :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_delete\_blocked#filter:extra\_blocked` or covered by a prefix.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the filter plugin. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
example: ``input | infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-extra_blocked"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked_filter__parameter-extra_blocked:

      .. rst-class:: ansible-option-title

      **extra_blocked**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-extra_blocked" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Extra namespace names to refuse, in addition to the built\-in control\-plane set.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-extra_prefixes"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked_filter__parameter-extra_prefixes:

      .. rst-class:: ansible-option-title

      **extra_prefixes**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-extra_prefixes" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Extra name prefixes to refuse. Matched with :literal:`startswith` after the name is lowercased.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-name"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked_filter__parameter-name:

      .. rst-class:: ansible-option-title

      **name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Namespace name ocp\_namespace would delete.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    {{ 'app' | infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked }}
    # false

    {{ 'kube-public' | infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked }}
    # true

    {{ 'team-app' | infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked([], ['team-']) }}
    # true



.. Facts


.. Return values

Return Value
------------

.. tabularcolumns:: \X{1}{3}\X{2}{3}

.. list-table::
  :width: 100%
  :widths: auto
  :header-rows: 1
  :class: longtable ansible-option-table

  * - Key
    - Description

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="return-_value"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_namespace_delete_blocked_filter__return-_value:

      .. rst-class:: ansible-option-title

      **Return value**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-_value" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Whether ocp\_namespace must refuse to delete :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_namespace\_delete\_blocked#filter:name`.


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` success


      .. raw:: html

        </div>



..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Automation Development Office


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
