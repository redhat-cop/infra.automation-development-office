.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.ado/edit/main/plugins/test/sample_test.py?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.24.0

.. Anchors

.. _ansible_collections.infra.ado.sample_test_test:

.. Anchors: short name for ansible.builtin

.. Title

infra.ado.sample_test test -- A custom test plugin for Ansible.
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This test plugin is part of the `infra.ado collection <https://galaxy.ansible.com/ui/repo/published/infra/ado/>`_ (version 1.0.0).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.ado`.

    To use it in a playbook, specify: :code:`infra.ado.sample_test`.

.. version_added

.. rst-class:: ansible-version-added

New in infra.ado 1.0.0

.. contents::
   :local:
   :depth: 1

.. Deprecated


Synopsis
--------

.. Description

- This is a demo test plugin designed to return a bool.


.. Aliases


.. Requirements






.. Options

Keyword parameters
------------------

This describes keyword parameters of the test. These are the values ``key1=value1``, ``key2=value2`` and so on in the following
examples: ``input is infra.ado.sample_test(key1=value1, key2=value2, ...)`` and ``input is not infra.ado.sample_test(key1=value1, key2=value2, ...)``

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
        <div class="ansibleOptionAnchor" id="parameter-name"></div>

      .. _ansible_collections.infra.ado.sample_test_test__parameter-name:

      .. rst-class:: ansible-option-title

      **name**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-name" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`boolean`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      This is a sample option.


      .. rst-class:: ansible-option-line

      :ansible-option-choices:`Choices:`

      - :ansible-option-choices-entry:`false`
      - :ansible-option-choices-entry:`true`


      .. raw:: html

        </div>


.. Attributes


.. Notes


.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    # sample_test test example

    - name: Display a bool
      ansible.builtin.debug:
        msg: "{{ 50 | sample_test }}"



.. Facts


.. Return values


..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Your Name


.. Extra links

Collection links
~~~~~~~~~~~~~~~~

.. ansible-links::

  - title: "Issue Tracker"
    url: "http://example.com/issue/tracker"
    external: true
  - title: "Homepage"
    url: "http://example.com"
    external: true
  - title: "Repository (Sources)"
    url: "http://example.com/repository"
    external: true
  - title: "Report an issue"
    url: "https://github.com/ansible-collections/infra.ado/issues/new/choose"
    external: true


.. Parsing errors
