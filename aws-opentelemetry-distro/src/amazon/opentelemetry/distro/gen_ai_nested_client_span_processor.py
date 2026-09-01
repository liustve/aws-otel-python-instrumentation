# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from amazon.opentelemetry.distro.instrumentation.common.instrumentation_utils import DictWithLock
from opentelemetry.sdk.trace import Span, SpanProcessor
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_OPERATION_NAME,
    GenAiOperationNameValues,
)
from opentelemetry.trace import SpanKind, get_current_span


class GenAiNestedClientSpanProcessor(SpanProcessor):
    # OTel GenAI semantic conventions require outgoing LLM calls to be CLIENT spans.
    # Allowlisted nested GenAI calls remain spans and demote the outer inference span
    # to INTERNAL. HTTP CLIENT children are folded into the inference span.

    def __init__(self):
        self._span_to_nearest_gen_ai_parent: DictWithLock = DictWithLock()

    def on_start(self, span: Span, parent_context=None) -> None:
        if span.kind != SpanKind.CLIENT:
            return

        parent_span = get_current_span(parent_context)
        if not isinstance(parent_span, Span):
            return

        if self.is_gen_ai_inference_span(parent_span):
            gen_ai_parent_span = parent_span
        else:
            gen_ai_parent_span = self._span_to_nearest_gen_ai_parent.get(parent_span)
            if gen_ai_parent_span is None:
                return

        self._span_to_nearest_gen_ai_parent.put(span, gen_ai_parent_span)

        if span.instrumentation_scope.name not in (
            "opentelemetry.instrumentation.aiohttp_client",
            "opentelemetry.instrumentation.httpx",
            "opentelemetry.instrumentation.requests",
            "opentelemetry.instrumentation.tornado",
            "opentelemetry.instrumentation.urllib",
            "opentelemetry.instrumentation.urllib3",
        ):
            return

        span._context = gen_ai_parent_span.get_span_context()  # noqa: SLF001
        # sampled=False would route this span to BatchUnsampledSpanProcessor.
        # Redirect Span.end here so no registered exporter or metrics processor sees it.
        span._span_processor = self  # noqa: SLF001

    def _on_ending(self, span: Span) -> None:
        parent_span = self._span_to_nearest_gen_ai_parent.pop(span)
        if parent_span is None:
            return

        if span._span_processor is not self:  # noqa: SLF001
            if self.is_gen_ai_inference_span(span):
                parent_span._kind = SpanKind.INTERNAL  # noqa: SLF001
            return

        self._copy_suppressed_client_attributes(span, parent_span)

    @staticmethod
    def is_gen_ai_inference_span(span) -> bool:
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
        self._span_to_nearest_gen_ai_parent.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # pylint: disable=no-self-use
        return True
