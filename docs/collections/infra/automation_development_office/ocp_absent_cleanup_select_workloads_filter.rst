.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.automation_development_office/edit/main/plugins/filter/ocp_absent_cleanup_select_workloads.yml?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.29.1

.. Anchors

.. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter:

.. Anchors: short name for ansible.builtin

.. Title

infra.automation_development_office.ocp_absent_cleanup_select_workloads filter -- Return workloads in a namespace that this run may delete
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This filter plugin is part of the `infra.automation_development_office collection <https://galaxy.ansible.com/ui/repo/published/infra/automation_development_office/>`_ (version 2.1.4).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.automation\_development\_office`.

    To use it in a playbook, specify: :code:`infra.automation_development_office.ocp_absent_cleanup_select_workloads`.

.. version_added


.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- An empty :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:names` list deletes nothing unless :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:authorize\_unfiltered` is :literal:`true`.
- When :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:names` is set, only objects whose metadata.name is in that list are returned.
- Objects whose metadata.namespace is some other namespace are never returned.
- Objects with an empty metadata.namespace are treated as already in :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:namespace`.
- An invalid :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:namespace` returns an empty list.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the filter plugin. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
example: ``input | infra.automation_development_office.ocp_absent_cleanup_select_workloads(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-authorize_unfiltered"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter__parameter-authorize_unfiltered:

      .. rst-class:: ansible-option-title

      **authorize_unfiltered**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-authorize_unfiltered" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Allow selection of every workload in :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:namespace` when :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:names` is empty.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry-default:`false` :ansible-option-choices-default-mark:`← (default)`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-names"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter__parameter-names:

      .. rst-class:: ansible-option-title

      **names**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-names" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      metadata.name values this run may delete.

      An empty list selects nothing unless :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:authorize\_unfiltered` is :literal:`true`.


      .. rst-class:: ansible-option-line

      :ansible-option-default-bold:`Default:` :ansible-option-default:`[]`

      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-namespace"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter__parameter-namespace:

      .. rst-class:: ansible-option-title

      **namespace**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-namespace" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Namespace this run may delete workloads from.


      .. raw:: html

        </div>

  * - .. raw:: html

        <div class="ansible-option-cell">
        <div class="ansibleOptionAnchor" id="parameter-resources"></div>

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter__parameter-resources:

      .. rst-class:: ansible-option-title

      **resources**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-resources" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=dictionary` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Workload objects to consider.


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    {{ workloads | infra.automation_development_office.ocp_absent_cleanup_select_workloads('app', ['api']) }}

    {{ workloads | infra.automation_development_office.ocp_absent_cleanup_select_workloads('app', [], true) }}



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

      .. _ansible_collections.infra.automation_development_office.ocp_absent_cleanup_select_workloads_filter__return-_value:

      .. rst-class:: ansible-option-title

      **Return value**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-_value" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=dictionary`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Workload objects in :ansopt:`infra.automation\_development\_office.ocp\_absent\_cleanup\_select\_workloads#filter:namespace` that this run may delete.


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
