# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
from dataclasses import dataclass
from unittest import TestCase
from unittest.mock import patch

from amazon.opentelemetry.distro.attribute_redacting_span_processor import (
    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES,
    ENV_ADOT_REDACT_SPAN_ATTRIBUTES,
    REDACTED_VALUE,
    AttributeRedactingSpanProcessor,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util.types import AttributeValue


@dataclass
class RedactionTestData:
    name: str
    environment_variables: dict[str, str]
    span_attributes: dict[str, AttributeValue]
    event_attributes: dict[str, AttributeValue]
    expected_span_attributes: dict[str, AttributeValue]
    expected_event_attributes: dict[str, AttributeValue]


class TestAttributeRedactingSpanProcessor(TestCase):
    def test_should_redact_all_attributes_that_match_configured_patterns(self):
        test_cases = (
            RedactionTestData(
                name="independent configured attribute names",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: (
                        " user.email, request.body, db.statement, gen_ai.prompt, user.email "
                    ),
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: " db.statement, event.secret ",
                },
                span_attributes={
                    "user.email": "user@example.com",
                    "request.body": '{"password":"secret"}',
                    "db.statement": "SELECT * FROM users",
                    "gen_ai.prompt": "private prompt",
                    "event.secret": "span value",
                    "http.request.method": "POST",
                    "server.address": "example.com",
                },
                event_attributes={
                    "user.email": "event-user@example.com",
                    "db.statement": "UPDATE users SET password = 'secret'",
                    "gen_ai.prompt": "private event prompt",
                    "event.secret": "event value",
                    "event.safe": "keep me",
                },
                expected_span_attributes={
                    "user.email": REDACTED_VALUE,
                    "request.body": REDACTED_VALUE,
                    "db.statement": REDACTED_VALUE,
                    "gen_ai.prompt": REDACTED_VALUE,
                    "event.secret": "span value",
                    "http.request.method": "POST",
                    "server.address": "example.com",
                },
                expected_event_attributes={
                    "user.email": "event-user@example.com",
                    "db.statement": REDACTED_VALUE,
                    "gen_ai.prompt": "private event prompt",
                    "event.secret": REDACTED_VALUE,
                    "event.safe": "keep me",
                },
            ),
            RedactionTestData(
                name="wildcard only",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "*",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "*",
                },
                span_attributes={"first": "secret", "second": 42, "third": True},
                event_attributes={"event.first": "secret", "event.second": 42},
                expected_span_attributes={
                    "first": REDACTED_VALUE,
                    "second": REDACTED_VALUE,
                    "third": REDACTED_VALUE,
                },
                expected_event_attributes={
                    "event.first": REDACTED_VALUE,
                    "event.second": REDACTED_VALUE,
                },
            ),
            RedactionTestData(
                name="prefix wildcard",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "http.*",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "http.*",
                },
                span_attributes={
                    "http.request.method": "GET",
                    "http.response.status_code": 200,
                    "server.address": "example.com",
                },
                event_attributes={
                    "http.request.header.authorization": "secret",
                    "event.safe": "keep me",
                },
                expected_span_attributes={
                    "http.request.method": REDACTED_VALUE,
                    "http.response.status_code": REDACTED_VALUE,
                    "server.address": "example.com",
                },
                expected_event_attributes={
                    "http.request.header.authorization": REDACTED_VALUE,
                    "event.safe": "keep me",
                },
            ),
            RedactionTestData(
                name="suffix wildcard",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "*.body",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "*.body",
                },
                span_attributes={"request.body": "secret", "response.body": "secret", "body.size": 42},
                event_attributes={"message.body": "secret", "message.body.size": 42},
                expected_span_attributes={
                    "request.body": REDACTED_VALUE,
                    "response.body": REDACTED_VALUE,
                    "body.size": 42,
                },
                expected_event_attributes={
                    "message.body": REDACTED_VALUE,
                    "message.body.size": 42,
                },
            ),
            RedactionTestData(
                name="multiple wildcard segments",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "gen_ai.*.content",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "gen_ai.*.content",
                },
                span_attributes={
                    "gen_ai.input.content": "secret input",
                    "gen_ai.output.content": "secret output",
                    "gen_ai.request.model": "model",
                },
                event_attributes={
                    "gen_ai.tool.content": "secret event",
                    "gen_ai.tool.name": "lookup",
                },
                expected_span_attributes={
                    "gen_ai.input.content": REDACTED_VALUE,
                    "gen_ai.output.content": REDACTED_VALUE,
                    "gen_ai.request.model": "model",
                },
                expected_event_attributes={
                    "gen_ai.tool.content": REDACTED_VALUE,
                    "gen_ai.tool.name": "lookup",
                },
            ),
            RedactionTestData(
                name="wildcard mixed with explicit names",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "user.email,http.*",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "user.email,http.*",
                },
                span_attributes={"user.email": "user@example.com", "http.route": "/users", "safe": "value"},
                event_attributes={
                    "user.email": "event-user@example.com",
                    "http.response.body": "secret",
                    "event.safe": "keep me",
                },
                expected_span_attributes={
                    "user.email": REDACTED_VALUE,
                    "http.route": REDACTED_VALUE,
                    "safe": "value",
                },
                expected_event_attributes={
                    "user.email": REDACTED_VALUE,
                    "http.response.body": REDACTED_VALUE,
                    "event.safe": "keep me",
                },
            ),
        )

        for test_data in test_cases:
            with self.subTest(name=test_data.name):
                self._assert_redaction(test_data)

    def test_should_not_redact_attributes_for_invalid_configured_patterns(self):
        test_cases = (
            RedactionTestData(
                name="empty configuration",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "",
                },
                span_attributes={"user.email": "user@example.com"},
                event_attributes={"user.email": "event-user@example.com"},
                expected_span_attributes={"user.email": "user@example.com"},
                expected_event_attributes={"user.email": "event-user@example.com"},
            ),
            RedactionTestData(
                name="empty comma-separated entries",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: " , , ",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: " , , ",
                },
                span_attributes={"request.body": "secret"},
                event_attributes={"request.body": "event secret"},
                expected_span_attributes={"request.body": "secret"},
                expected_event_attributes={"request.body": "event secret"},
            ),
            RedactionTestData(
                name="whitespace-only configuration",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: " \t ",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: " \t ",
                },
                span_attributes={"db.statement": "SELECT * FROM users"},
                event_attributes={"db.statement": "DELETE FROM users"},
                expected_span_attributes={"db.statement": "SELECT * FROM users"},
                expected_event_attributes={"db.statement": "DELETE FROM users"},
            ),
            RedactionTestData(
                name="unsupported regular expression",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: r"http\.request\..+",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: r"http\.request\..+",
                },
                span_attributes={"http.request.method": "POST"},
                event_attributes={"http.request.body": "secret"},
                expected_span_attributes={"http.request.method": "POST"},
                expected_event_attributes={"http.request.body": "secret"},
            ),
            RedactionTestData(
                name="unsupported regular expression anchors",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "^user.email$",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "^user.email$",
                },
                span_attributes={"user.email": "user@example.com"},
                event_attributes={"user.email": "event-user@example.com"},
                expected_span_attributes={"user.email": "user@example.com"},
                expected_event_attributes={"user.email": "event-user@example.com"},
            ),
            RedactionTestData(
                name="unsupported regular expression character class",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "http.request.[a-z]+",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "http.request.[a-z]+",
                },
                span_attributes={"http.request.method": "POST"},
                event_attributes={"http.request.body": "secret"},
                expected_span_attributes={"http.request.method": "POST"},
                expected_event_attributes={"http.request.body": "secret"},
            ),
            RedactionTestData(
                name="unsupported regular expression alternation",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "user.email|request.body",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "user.email|request.body",
                },
                span_attributes={
                    "user.email": "user@example.com",
                    "request.body": "secret",
                },
                event_attributes={
                    "user.email": "event-user@example.com",
                    "request.body": "event secret",
                },
                expected_span_attributes={
                    "user.email": "user@example.com",
                    "request.body": "secret",
                },
                expected_event_attributes={
                    "user.email": "event-user@example.com",
                    "request.body": "event secret",
                },
            ),
            RedactionTestData(
                name="unsupported question mark wildcard",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "http.request.?",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "http.request.?",
                },
                span_attributes={"http.request.method": "POST"},
                event_attributes={"http.request.body": "secret"},
                expected_span_attributes={"http.request.method": "POST"},
                expected_event_attributes={"http.request.body": "secret"},
            ),
            RedactionTestData(
                name="malformed bracket pattern",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "http.request.[",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "http.request.[",
                },
                span_attributes={"http.request.method": "POST"},
                event_attributes={"http.request.body": "secret"},
                expected_span_attributes={"http.request.method": "POST"},
                expected_event_attributes={"http.request.body": "secret"},
            ),
            RedactionTestData(
                name="attribute name containing comma",
                environment_variables={
                    ENV_ADOT_REDACT_SPAN_ATTRIBUTES: "custom,attribute",
                    ENV_ADOT_REDACT_SPAN_EVENT_ATTRIBUTES: "custom,attribute",
                },
                span_attributes={"custom,attribute": "secret"},
                event_attributes={"custom,attribute": "event secret"},
                expected_span_attributes={"custom,attribute": "secret"},
                expected_event_attributes={"custom,attribute": "event secret"},
            ),
        )

        for test_data in test_cases:
            with self.subTest(name=test_data.name):
                self._assert_redaction(test_data)

    def _assert_redaction(self, test_data: RedactionTestData) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        with patch.dict(os.environ, test_data.environment_variables):
            provider.add_span_processor(AttributeRedactingSpanProcessor())
        provider.add_span_processor(BatchSpanProcessor(exporter))
        tracer = provider.get_tracer(__name__)

        try:
            with tracer.start_as_current_span("test", attributes=test_data.span_attributes) as span:
                span.add_event("test.event", attributes=test_data.event_attributes)

            self.assertTrue(provider.force_flush())
            finished_spans = exporter.get_finished_spans()
            self.assertEqual(len(finished_spans), 1)
            exported_span = finished_spans[0]
            self.assertEqual(dict(exported_span.attributes), test_data.expected_span_attributes)
            self.assertEqual(
                {event.name: dict(event.attributes) for event in exported_span.events},
                {"test.event": test_data.expected_event_attributes},
            )
        finally:
            provider.shutdown()
