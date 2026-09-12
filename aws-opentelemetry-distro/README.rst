AWS Distro For OpenTelemetry Python Distro
============================================

Installation
------------

::

    pip install aws-opentelemetry-distro


This package provides Amazon Web Services distribution of the OpenTelemetry Python Instrumentation, which allows for auto-instrumentation of Python applications.

GenAI instrumentation environment variables
--------------------------------------------

``ADOT_GENAI_INSTRUMENTATION``
    Controls AWS native GenAI instrumentations when agent observability is enabled. Supported values are ``auto``
    (default), ``enabled``, and ``disabled``. ``AWS_AGENTIC_INSTRUMENTATION`` is a deprecated alias.

``ADOT_INSTRUMENTATION_MCP_SUPPRESS_HTTP_INSTRUMENTATION``
    Controls whether MCP instrumentation suppresses HTTP client and ASGI spans. The default is ``true``.
    ``OTEL_MCP_SUPPRESS_HTTP_INSTRUMENTATION`` is a deprecated alias.

``ADOT_INSTRUMENTATION_OPENAI_AGENTS_DISABLE_TRACE_EXPORT``
    Set to ``true`` to prevent the OpenAI Agents SDK from exporting traces to the OpenAI backend while retaining
    ADOT instrumentation. The default is ``false``.

References
----------

* `OpenTelemetry Project <https://opentelemetry.io/>`_
* `Example using opentelemetry-distro <https://opentelemetry.io/docs/instrumentation/python/distro/>`_
