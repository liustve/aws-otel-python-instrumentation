# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from urllib.parse import urlparse

from amazon.opentelemetry.distro.instrumentation.common.instrumentation_utils import DictWithLock
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_OPERATION_NAME,
    GenAiOperationNameValues,
)
from opentelemetry.semconv._incubating.attributes.http_attributes import HTTP_STATUS_CODE, HTTP_URL
from opentelemetry.semconv.attributes.http_attributes import HTTP_RESPONSE_STATUS_CODE
from opentelemetry.semconv.attributes.server_attributes import SERVER_ADDRESS, SERVER_PORT
from opentelemetry.semconv.attributes.url_attributes import URL_FULL
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags, get_current_span

_LLM_OPERATION_NAMES = (
    GenAiOperationNameValues.CHAT.value,
    GenAiOperationNameValues.TEXT_COMPLETION.value,
    GenAiOperationNameValues.GENERATE_CONTENT.value,
    GenAiOperationNameValues.EMBEDDINGS.value,
)
_DEFAULT_PORTS = {"http": 80, "https": 443}


class GenAiNestedClientSpanProcessor(SpanProcessor):
    # OTel GenAI semantic conventions require outgoing LLM calls to be CLIENT spans.
    # Allowlisted nested GenAI calls remain spans and demote the outer inference span
    # to INTERNAL. All other CLIENT children are folded into the inference span.

    def __init__(self):
        self._has_gen_ai_client_child: DictWithLock = DictWithLock()
        self._parent_spans: DictWithLock = DictWithLock()
        self._span_states: DictWithLock = DictWithLock()

    def on_start(self, span: Span, parent_context=None) -> None:
        if span.kind != SpanKind.CLIENT:
            return

        parent_span = get_current_span(parent_context)
        if not isinstance(parent_span, Span):
            return
        if (parent_span.attributes or {}).get(GEN_AI_OPERATION_NAME) not in _LLM_OPERATION_NAMES:
            return

        # A nested inference span may not receive its operation attribute until
        # after on_start. Restore its unique id before its child propagates.
        parent_state = self._span_states.get(id(parent_span))
        if parent_state:
            parent_span._context = parent_state[1]  # noqa: SLF001
            span._parent = parent_span.get_span_context()  # noqa: SLF001

        child_span_id = span.context.span_id
        self._parent_spans.put(child_span_id, parent_span)

        original_context = span.context
        self._span_states.put(
            id(span),
            (child_span_id, original_context, span._span_processor),  # noqa: SLF001
        )
        span._context = parent_span.get_span_context()  # noqa: SLF001
        # Span.end dispatches through this per-span reference. Withholding a
        # confirmed shadow here prevents every registered on_end consumer from
        # seeing it, regardless of processor order or sampling polarity.
        span._span_processor = self  # noqa: SLF001

    def _on_ending(self, span: Span) -> None:
        span_state = self._span_states.pop(id(span))
        if span_state is None:
            return

        child_span_id, original_context, original_processor = span_state
        parent_span = self._parent_spans.pop(child_span_id)
        if self._is_allowlisted_gen_ai_span(span):
            span._context = original_context  # noqa: SLF001
            span._span_processor = original_processor  # noqa: SLF001
            original_processor._on_ending(span)  # noqa: SLF001
            return

        span._context = SpanContext(  # noqa: SLF001
            trace_id=span.context.trace_id,
            span_id=span.context.span_id,
            is_remote=span.context.is_remote,
            trace_flags=TraceFlags(span.context.trace_flags & ~TraceFlags.SAMPLED),
            trace_state=span.context.trace_state,
        )
        if parent_span is not None:
            self._copy_suppressed_client_attributes(span, parent_span)

    def on_end(self, span: ReadableSpan) -> None:
        if span.kind != SpanKind.CLIENT:
            return

        is_llm_span = (span.attributes or {}).get(GEN_AI_OPERATION_NAME) in _LLM_OPERATION_NAMES

        # Only an allowlisted nested GenAI span is forwarded through the original
        # processor chain and can demote its parent.
        parent_span_id = span.parent.span_id if span.parent else None
        if is_llm_span and parent_span_id:
            self._has_gen_ai_client_child.put(parent_span_id, True)

        if is_llm_span and span.context and self._has_gen_ai_client_child.pop(span.context.span_id):
            span._kind = SpanKind.INTERNAL  # noqa: SLF001

    @staticmethod
    def _is_allowlisted_gen_ai_span(span) -> bool:
        return (span.attributes or {}).get(GEN_AI_OPERATION_NAME) in _LLM_OPERATION_NAMES

    @staticmethod
    def _copy_suppressed_client_attributes(span: Span, parent_span: Span) -> None:
        attributes = dict(span.attributes or {})
        parent_span.set_attributes(attributes)

        url = attributes.get(URL_FULL) or attributes.get(HTTP_URL)
        if not url:
            return

        parent_span.set_attribute(URL_FULL, url)
        parsed_url = urlparse(url)
        if parsed_url.hostname:
            parent_span.set_attribute(SERVER_ADDRESS, parsed_url.hostname)
        try:
            port = parsed_url.port or _DEFAULT_PORTS.get(parsed_url.scheme)
        except ValueError:
            port = None
        if port:
            parent_span.set_attribute(SERVER_PORT, port)

        status_code = attributes.get(HTTP_RESPONSE_STATUS_CODE) or attributes.get(HTTP_STATUS_CODE)
        if status_code is not None:
            parent_span.set_attribute(HTTP_RESPONSE_STATUS_CODE, status_code)

    def shutdown(self) -> None:
        self._has_gen_ai_client_child.clear()
        self._parent_spans.clear()
        self._span_states.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # pylint: disable=no-self-use
        return True
