# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from amazon.opentelemetry.distro.instrumentation.common.instrumentation_utils import DictWithLock
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_OPERATION_NAME,
    GenAiOperationNameValues,
)
from opentelemetry.trace import SpanContext, SpanKind, TraceFlags, get_current_span


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
        if not self._is_allowlisted_gen_ai_span(parent_span):
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

        # Only an allowlisted nested GenAI span is forwarded through the original
        # processor chain and can demote its parent.
        parent_span_id = span.parent.span_id if span.parent else None
        if self._is_allowlisted_gen_ai_span(span) and parent_span_id:
            self._has_gen_ai_client_child.put(parent_span_id, True)

        if (
            self._is_allowlisted_gen_ai_span(span)
            and span.context
            and self._has_gen_ai_client_child.pop(span.context.span_id)
        ):
            span._kind = SpanKind.INTERNAL  # noqa: SLF001

    @staticmethod
    def _is_allowlisted_gen_ai_span(span) -> bool:
        return (span.attributes or {}).get(GEN_AI_OPERATION_NAME) in (
            GenAiOperationNameValues.CHAT.value,
            GenAiOperationNameValues.TEXT_COMPLETION.value,
            GenAiOperationNameValues.GENERATE_CONTENT.value,
            GenAiOperationNameValues.EMBEDDINGS.value,
        )

    @staticmethod
    def _copy_suppressed_client_attributes(span: Span, parent_span: Span) -> None:
        parent_span.set_attributes(
            {
                key: value
                for key, value in (span.attributes or {}).items()
                if key == "error.type"
                or key.startswith(("http.", "url.", "server.", "network.", "user_agent.", "net."))
            }
        )

    def shutdown(self) -> None:
        self._has_gen_ai_client_child.clear()
        self._parent_spans.clear()
        self._span_states.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # pylint: disable=no-self-use
        return True
