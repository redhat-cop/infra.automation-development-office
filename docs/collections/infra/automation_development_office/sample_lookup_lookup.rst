.. Document meta

:orphan:
:github_url: https://github.com/ansible-collections/infra.ado/edit/main/plugins/lookup/sample_lookup.py?description=%23%23%23%23%23%20SUMMARY%0A%3C!---%20Your%20description%20here%20--%3E%0A%0A%0A%23%23%23%23%23%20ISSUE%20TYPE%0A-%20Docs%20Pull%20Request%0A%0A%2Blabel:%20docsite_pr

.. |antsibull-internal-nbsp| unicode:: 0xA0
    :trim:

.. meta::
  :antsibull-docs: 2.24.0

.. Anchors

.. _ansible_collections.infra.ado.sample_lookup_lookup:

.. Anchors: short name for ansible.builtin

.. Title

infra.ado.sample_lookup lookup -- A custom lookup plugin for Ansible.
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. Collection note

.. note::
    This lookup plugin is part of the `infra.ado collection <https://galaxy.ansible.com/ui/repo/published/infra/ado/>`_ (version 1.0.0).

    It is not included in ``ansible-core``.
    To check whether it is installed, run :code:`ansible-galaxy collection list`.

    To install it, use: :code:`ansible\-galaxy collection install infra.ado`.

    To use it in a playbook, specify: :code:`infra.ado.sample_lookup`.

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

- This is a custom lookup plugin to provide lookup functionality.


.. Aliases


.. Requirements




.. Terms

Terms
-----

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
        <div class="ansibleOptionAnchor" id="parameter-_terms"></div>

      .. _ansible_collections.infra.ado.sample_lookup_lookup__parameter-_terms:

      .. rst-class:: ansible-option-title

      **Terms**

      .. raw:: html

        <a class="ansibleOptionLink" href="#parameter-_terms" title="Permalink to this option"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`string` / :ansible-option-required:`required`




      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      Terms to lookup


      .. raw:: html

        </div>





.. Options


.. Attributes


.. Notes

Notes
-----

.. note::
   - This is a scaffold template. Customize the plugin to fit your needs.

.. Seealso


.. Examples

Examples
--------

.. code-block:: yaml+jinja

    - name: Example usage of sample_lookup
      ansible.builtin.debug:
        msg: "{{ lookup('sample_lookup', 'example_term') }}"



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
        <div class="ansibleOptionAnchor" id="return-_list"></div>

      .. _ansible_collections.infra.ado.sample_lookup_lookup__return-_list:

      .. rst-class:: ansible-option-title

      **Return value**

      .. raw:: html

        <a class="ansibleOptionLink" href="#return-_list" title="Permalink to this return value"></a>

      .. ansible-option-type-line::

        :ansible-option-type:`list` / :ansible-option-elements:`elements=string`

      .. raw:: html

        </div>

    - .. raw:: html

        <div class="ansible-option-cell">

      The list of values found by the lookup


      .. rst-class:: ansible-option-line

      :ansible-option-returned-bold:`Returned:` success


      .. raw:: html

        </div>



..  Status (Presently only deprecated)


.. Authors

Authors
~~~~~~~

- Your Name (@username)


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
