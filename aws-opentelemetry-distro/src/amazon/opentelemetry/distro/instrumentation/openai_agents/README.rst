AWS Distro for OpenTelemetry OpenAI Agents Instrumentation
===========================================================

This instrumentation traces applications built with the
`OpenAI Agents SDK <https://github.com/openai/openai-agents-python>`_ and emits
telemetry that follows OpenTelemetry's Generative AI semantic conventions.

Features
--------

* Creates spans for agents, model generations, tools, and handoffs.
* Records model, token usage, message, tool, and operation attributes when they
  are available from the Agents SDK.

Installation
------------

Install the distribution and a supported OpenAI Agents SDK version:

::

    pip install aws-opentelemetry-distro "openai-agents>=0.3.3,<1"

Usage
-----

The instrumentation is registered with OpenTelemetry Python auto-instrumentation
and is loaded when the OpenAI Agents SDK is installed:

::

    opentelemetry-instrument python app.py

No application tracing code or Agents SDK trace processor registration is
required.

Configuration
-------------

    **Note**

    Set ``ADOT_INSTRUMENTATION_OPENAI_AGENTS_DISABLE_TRACE_EXPORT=true`` to
    disable exporting traces to the OpenAI backend while retaining ADOT
    instrumentation:

    ::

        export ADOT_INSTRUMENTATION_OPENAI_AGENTS_DISABLE_TRACE_EXPORT=true

Disable the instrumentation
---------------------------

Add ``aws_openai_agents`` to ``OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`` before
starting the application. Include any other disabled instrumentations in the
same comma-separated value:

::

    export OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=aws_openai_agents
    opentelemetry-instrument python app.py

References
----------

* `OpenTelemetry GenAI agent spans semantic conventions <https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md>`_
* `OpenAI Agents SDK documentation <https://openai.github.io/openai-agents-python/>`_
