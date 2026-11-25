.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/filter/ocp_absent_cleanup_csv_name_matches.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_csv_name_matches_filter:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.ocp_absent_cleanup_csv_name_matches filter -- Return whether a CSV name is an exact or package.version match
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This filter plugin is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.ocp_absent_cleanup_csv_name_matches`.

.. version_added


.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- Return :literal:`true` when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:csv\_name` equals :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:match`.
- Also return :literal:`true` when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:csv\_name` is :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:match` plus a dot and a version, such as :literal:`cert\-manager\-operator.v1.20.1` for :literal:`cert\-manager\-operator`.
- A longer package name such as :literal:`cert\-manager\-operator\-extra.v1` does not match :literal:`cert\-manager\-operator`.
- A name that only contains the token, such as :literal:`openshift\-gitops\-operator.v1.21.1` for :literal:`operator`\ , does not match.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the filter plugin. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
example: ``input | infra.automation_development_office.ocp_absent_cleanup_csv_name_matches(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-csv_name"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_csv_name_matches_filter__parameter-csv_name:

      .. rst-class:: ansible-option-title

      **csv_name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-csv_name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      ClusterServiceVersion metadata.name.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-match"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_csv_name_matches_filter__parameter-match:

      .. rst-class:: ansible-option-title

      **match**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-match" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Exact CSV name or package name to compare.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    {{ 'cert-manager-operator.v1.20.1' | infra.automation_development_office.ocp_absent_cleanup_csv_name_matches('cert-manager-operator') }}
    # true

    {{ 'openshift-gitops-operator.v1.21.1' | infra.automation_development_office.ocp_absent_cleanup_csv_name_matches('operator') }}
    # false



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

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_csv_name_matches_filter__return-_value:

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

      Whether :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:csv\_name` matches :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_csv\_name\_matches#filter:match`.


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
