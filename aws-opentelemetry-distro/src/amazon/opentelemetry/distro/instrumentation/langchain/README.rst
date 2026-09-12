AWS Distro for OpenTelemetry LangChain Instrumentation
=======================================================

This instrumentation traces applications built with
`LangChain <https://www.langchain.com/>`_ and emits telemetry that follows
OpenTelemetry's Generative AI semantic conventions.

Features
--------

* Creates spans for chains, agents, model calls, and tools.
* Records model, token usage, message, tool, and operation attributes when they
  are available from LangChain callbacks.

Installation
------------

Install the distribution and a supported LangChain version:

::

    pip install aws-opentelemetry-distro "langchain>=0.3.21,<2"

Usage
-----

The instrumentation is registered with OpenTelemetry Python auto-instrumentation
and is loaded when LangChain is installed:

::

    opentelemetry-instrument python app.py

.. pull-quote::

    **Note**

We recommend setting ``LANGFUSE_TRACING_ENABLED=false`` if you are using
Langfuse with LangChain. This disables Langfuse tracing and prevents
conflicting instrumentation or duplicate telemetry.

::

    export LANGFUSE_TRACING_ENABLED=false

Disable the instrumentation
---------------------------

Add ``aws_langchain`` to ``OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`` before
starting the application. Include any other disabled instrumentations in the
same comma-separated value:

::

    export OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=aws_langchain
    opentelemetry-instrument python app.py

References
----------

* `OpenTelemetry GenAI agent spans semantic conventions <https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md>`_
* `LangChain documentation <https://python.langchain.com/docs/>`_
