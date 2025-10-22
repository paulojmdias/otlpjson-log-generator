#!/usr/bin/env python3

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from pydoc import locate
from typing import TYPE_CHECKING

from google.protobuf.json_format import MessageToJson
from opentelemetry.exporter.otlp.proto.common._log_encoder import encode_logs
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.sdk._logs import LogData, LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import LogExporter, BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_DEFAULT_LOG_HANDLER_KWARGS = {
    "maxBytes": 5 * 1024 * 1024,  # 5 MB
    "backupCount": 5,  # Keep 5 backup files
}

class OTLPJsonFileExporter(LogExporter):
    """A custom log exporter that writes logs in OTLP/JSON format to a file.

    Based on https://github.com/open-telemetry/opentelemetry-python/issues/4661
    """

    def __init__(
        self,
        log_path: str | Path = "logs/otel/service.log",  # Default log path
        log_handler_cls: str = "logging.handlers.RotatingFileHandler",
        log_handler_kwargs: dict | None = None,
    ) -> None:
        """Initialize the OTLPJsonFileExporter."""
        self.log_path = log_path

        log_handler_kwargs = log_handler_kwargs if isinstance(log_handler_kwargs, dict) else _DEFAULT_LOG_HANDLER_KWARGS

        # Make sure the directory exists
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("OTLPJsonFileExporter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # Prevent double logging

        handler = logging.Handler()

        if not self.logger.handlers:
            # If path is "stdout", use StreamHandler, otherwise use the specified handler class
            if self.log_path == "stdout":
                handler = logging.StreamHandler(sys.stdout)
            else:
                klass = locate(log_handler_cls)
                if not (
                    isinstance(klass, type)
                    and issubclass(
                        klass,
                        (
                            logging.handlers.RotatingFileHandler,
                            logging.handlers.TimedRotatingFileHandler,
                            logging.handlers.WatchedFileHandler,
                        ),
                    )
                ):
                    msg = (
                        f"Invalid log handler class: {log_handler_cls}. must be a "
                        "`logging.handlers.RotatingFileHandler` or `logging.handlers.TimedRotatingFileHandler` "
                        "or `logging.handlers.WatchedFileHandler`."
                    )

                handler = klass(self.log_path, **log_handler_kwargs)

            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _translate_data(self, data: Sequence[LogData]) -> ExportLogsServiceRequest:
        return encode_logs(data)

    def shutdown(self) -> None:
        """Shutdown the exporter."""

    def export(self, batch: Sequence[LogData]) -> None:
        """Export logs to a file in OTLP/JSON format."""
        service_request = self._translate_data(batch)
        json_str = MessageToJson(service_request, preserving_proto_field_name=True, indent=None)

        try:
            self.logger.info(json_str)
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            logger.warning(
                "Failed to write logs to file: %s. Error: %s",
                self.log_path,
                e,
            )


def setup_logging(export_path="my_service.log"):
    """
    Configure OpenTelemetry logging to export logs as OTLP JSON.
    """
    # Define basic resource attributes for the service
    resource = Resource.create(
        {
            "service.name": "example-service",
            "service.version": "1.0.0",
            "deployment.environment": "dev",
            "jurisdiction": "jur",
            "provider": "provider",
            "role": "role",
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
            "key4": "value4",
            "key5": "value5",
            "key6": "value6",
            "key7": "value7",
            "key8": "value8",
            "key8": "value9",
        }
    )

    # Create LoggerProvider and exporter
    provider = LoggerProvider(resource=resource)
    exporter = OTLPJsonFileExporter(
        log_path=export_path,
        log_handler_cls="logging.handlers.WatchedFileHandler",
        log_handler_kwargs={
            "mode": "a",
        },
    )

    # Add processor (batching recommended)
    processor = BatchLogRecordProcessor(exporter)
    provider.add_log_record_processor(processor)

    # Register global logger provider
    handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    return logging.getLogger(__name__)

if __name__ == "__main__":
    import time
    import itertools
    import random

    logger = setup_logging(export_path="/app/logs/service.log")

    # Optional: a few sample messages to rotate through
    MESSAGES = [
        ("info", "Service heartbeat OK."),
        ("warning", "Slow response from dependency."),
        ("error", "Transient failure processing request."),
    ]

    # Infinite loop with gentle pacing; Ctrl+C to stop
    try:
        for i in itertools.count(1):
            level, msg = random.choice(MESSAGES)

            # Attach some structured fields that will end up in OTLP JSON
            extra = {
                "request_id": f"req-{i:06d}",
                "user_id": random.randint(1, 1000),
                "latency_ms": random.randint(5, 500),
            }

            if level == "info":
                logger.info(msg, extra=extra)
            elif level == "warning":
                logger.warning(msg, extra=extra)
            else:
                logger.error(msg, extra={**extra, "error_code": random.choice([400, 404, 500, 503])})

            # Adjust the sleep to control log rate
            time.sleep(0.5)
    except KeyboardInterrupt:
        # Let the process exit cleanly on Ctrl+C
        pass
