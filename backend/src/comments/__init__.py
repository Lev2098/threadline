"""Comments bounded context.

Layout follows hexagonal architecture (ports & adapters):

* ``comments.domain``      - pure business model, no framework imports;
* ``comments.application`` - use cases and the ports they depend on;
* ``comments.adapters``    - Django / Redis / Celery / Elasticsearch implementations;
* ``comments.bootstrap``   - composition root wiring adapters into use cases.

The dependency rule (domain <- application <- adapters) is enforced by
import-linter, see ``backend/.importlinter``.
"""
