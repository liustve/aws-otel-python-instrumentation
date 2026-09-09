# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any, Optional

from opentelemetry import context


class PregelWrapper:
    """Wrap LangGraph's Pregel runtime so agents built with StateGraph can be classified as agent spans.

    https://docs.langchain.com/oss/python/langgraph/graph-api
    """

    _CONTEXT_KEY = "amazon.langchain.langgraph.pregel.agent_name"

    def __init__(self, is_async: bool = False):
        self.is_async = is_async

    def __call__(self, wrapped, instance, args, kwargs):
        graph_name = self._get_graph_name(instance, args, kwargs)
        if self.is_async:
            iterator = wrapped(*args, **kwargs).__aiter__()
            return self._aiterate_with_graph_context(iterator, graph_name)

        iterator = iter(wrapped(*args, **kwargs))
        return self._iterate_with_graph_context(iterator, graph_name)

    @classmethod
    def get_active_agent_name(cls) -> Optional[str]:
        """Return the name of the LangGraph currently executing through Pregel."""
        value = context.get_value(cls._CONTEXT_KEY)
        return value if isinstance(value, str) else None

    @staticmethod
    def _get_graph_name(instance: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Resolve the graph name using the same precedence as LangGraph."""
        config = args[1] if len(args) > 1 else kwargs.get("config")
        if isinstance(config, dict) and (run_name := config.get("run_name")):
            return str(run_name)

        instance_config = getattr(instance, "config", None)
        if isinstance(instance_config, dict) and (run_name := instance_config.get("run_name")):
            return str(run_name)

        get_name = getattr(instance, "get_name", None)
        if callable(get_name):
            try:
                if graph_name := get_name():
                    return str(graph_name)
            except Exception:  # pylint: disable=broad-except
                pass

        return "LangGraph"

    @classmethod
    def _iterate_with_graph_context(cls, iterator: Iterator[Any], graph_name: str) -> Iterator[Any]:
        while True:
            token = context.attach(context.set_value(cls._CONTEXT_KEY, graph_name))
            try:
                item = next(iterator)
            except StopIteration:
                return
            finally:
                context.detach(token)
            yield item

    @classmethod
    async def _aiterate_with_graph_context(cls, iterator: AsyncIterator[Any], graph_name: str) -> AsyncIterator[Any]:
        while True:
            token = context.attach(context.set_value(cls._CONTEXT_KEY, graph_name))
            try:
                item = await anext(iterator)
            except StopAsyncIteration:
                return
            finally:
                context.detach(token)
            yield item
