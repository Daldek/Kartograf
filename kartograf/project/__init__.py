"""Project manifest ``kartograf-project.json`` (ADR-040).

A project records which data its analysis ordered (tasks: data commands of
the CLI groups with their options) and exactly which store versions it used
(pinned files with SHA-256), so the data can be verified, checked for newer
source content and restored in another store.
"""
