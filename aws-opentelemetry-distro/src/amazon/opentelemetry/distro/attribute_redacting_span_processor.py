# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import re
from collections.abc import MutableMapping
from typing import Collection, Optional

from typing_extensions import override

from opentelemetry.attributes import BoundedAttributes
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.util import types

ENV_ADOT_REDACT_SPAN_ATTRIBUTES = "ADOT_REDACT_SPAN_ATTRIBUTES"
ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES = "ADOT_REDACT_SPAN_EVENT_ATTRIBUTES"
REDACTED_VALUE = "REDACTED"


class AttributeRedactingSpanProcessor(SpanProcessor):
    """
    Redacts separately configured attributes on completed spans and span events.

    Span and span event attribute names can be supplied to the constructor or
    through the ``ADOT_REDACT_SPAN_ATTRIBUTES`` and
    ``ADOT_REDACT_SPAN_EVENT_ATTRIBUTES`` environment variables as
    comma-separated lists. Each entry can be an exact attribute name or contain
    ``*`` wildcards. Matching attribute values are replaced with ``REDACTED`` in
    place while attribute names and non-matching values remain unchanged.

    Examples:
        Redact several exact span attributes and every span attribute beginning
        with ``http.request.``:

        ``ADOT_REDACT_SPAN_ATTRIBUTES=user.email,request.body,db.statement,http.request.*``

        Redact matching GenAI content attributes from span events:

        ``ADOT_REDACT_SPAN_EVENT_ATTRIBUTES=gen_ai.*.content``

        Redact every span attribute and every span event attribute:

        ``ADOT_REDACT_SPAN_ATTRIBUTES=*``
        ``ADOT_REDACT_SPAN_EVENT_ATTRIBUTES=*``
    """

    def __init__(
        self,
        span_attributes_to_redact: Optional[Collection[str]] = None,
        span_event_attributes_to_redact: Optional[Collection[str]] = None,
    ) -> None:
        self.span_attributes_to_redact = (
            list(span_attributes_to_redact)
            if span_attributes_to_redact
            else [
                attribute.strip()
                for attribute in os.environ.get(ENV_ADOT_REDACT_SPAN_ATTRIBUTES, "").split(",")
                if attribute.strip()
            ]
        )
        self.span_event_attributes_to_redact = (
            list(span_event_attributes_to_redact)
            if span_event_attributes_to_redact
            else [
                attribute.strip()
                for attribute in os.environ.get(ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES, "").split(",")
                if attribute.strip()
            ]
        )
        self._compiled_span_attribute_patterns = tuple(
            re.compile(re.escape(attribute).replace(r"\*", ".*")) for attribute in self.span_attributes_to_redact
        )
        self._compiled_span_event_attribute_patterns = tuple(
            re.compile(re.escape(attribute).replace(r"\*", ".*")) for attribute in self.span_event_attributes_to_redact
        )

    # pylint: disable=no-self-use
    @override
    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        return

    @override
    def on_end(self, span: ReadableSpan) -> None:
        if not self.span_attributes_to_redact and not self.span_event_attributes_to_redact:
            return

        if self.span_attributes_to_redact:
            self._redact_attributes(  # noqa: SLF001
                span._attributes,
                self._compiled_span_attribute_patterns,
            )

        if self.span_event_attributes_to_redact:
            for event in span.events:
                self._redact_attributes(  # noqa: SLF001
                    event._attributes,
                    self._compiled_span_event_attribute_patterns,
                )

    def _redact_attributes(
        self,
        attributes: types.Attributes,
        compiled_patterns: Collection[re.Pattern[str]],
    ) -> None:
        if not attributes:
            return

        if isinstance(attributes, BoundedAttributes):
            # Completed spans and events expose immutable BoundedAttributes, so
            # their public setter raises TypeError. Update existing values under its lock.
            with attributes._lock:  # noqa: SLF001
                for key in attributes._dict:  # noqa: SLF001
                    if self._should_redact(key, compiled_patterns):
                        attributes._dict[key] = REDACTED_VALUE  # noqa: SLF001
        elif isinstance(attributes, MutableMapping):
            for key in attributes:
                if self._should_redact(key, compiled_patterns):
                    attributes[key] = REDACTED_VALUE

    @staticmethod
    def _should_redact(attribute_name: str, compiled_patterns: Collection[re.Pattern[str]]) -> bool:
        return any(pattern.fullmatch(attribute_name) for pattern in compiled_patterns)

    # pylint: disable=no-self-use
    @override
    def shutdown(self) -> None:
        return

    # pylint: disable=no-self-use
    @override
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
