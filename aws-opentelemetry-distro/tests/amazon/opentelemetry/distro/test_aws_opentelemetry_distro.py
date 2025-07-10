# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import importlib
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from unittest import TestCase
from unittest.mock import patch

from amazon.opentelemetry.distro.aws_opentelemetry_distro import AwsOpenTelemetryDistro
from opentelemetry import propagate
from opentelemetry.propagators.composite import CompositePropagator


class TestAwsOpenTelemetryDistro(TestCase):
    def setUp(self):
        # Store original env vars if they exist
        self.env_vars_to_restore = {}
        self.env_vars_to_check = [
            "OTEL_EXPORTER_OTLP_PROTOCOL",
            "OTEL_PROPAGATORS",
            "OTEL_PYTHON_ID_GENERATOR",
            "OTEL_EXPORTER_OTLP_METRICS_DEFAULT_HISTOGRAM_AGGREGATION",
            "AGENT_OBSERVABILITY_ENABLED",
            "OTEL_TRACES_EXPORTER",
            "OTEL_LOGS_EXPORTER",
            "OTEL_METRICS_EXPORTER",
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
            "OTEL_TRACES_SAMPLER",
            "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS",
            "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED",
            "OTEL_AWS_APPLICATION_SIGNALS_ENABLED",
        ]

        # First, save all current values
        for var in self.env_vars_to_check:
            if var in os.environ:
                self.env_vars_to_restore[var] = os.environ[var]

        # Then clear ALL of them to ensure clean state
        for var in self.env_vars_to_check:
            if var in os.environ:
                del os.environ[var]

        # Preserve the original sys.path
        self.original_sys_path = sys.path.copy()

    def tearDown(self):
        # Clear all env vars first
        for var in self.env_vars_to_check:
            if var in os.environ:
                del os.environ[var]

        # Then restore original values
        for var, value in self.env_vars_to_restore.items():
            os.environ[var] = value

        # Restore the original sys.path
        sys.path[:] = self.original_sys_path

    def test_package_available(self):
        try:
            require(["aws-opentelemetry-distro-genai-beta"])
        except DistributionNotFound:
            self.fail("aws-opentelemetry-distro-genai-beta not installed")
