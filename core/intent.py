"""Replaceable fast-path classifier; None delegates to the existing model path."""
from __future__ import annotations

from typing import Any, Protocol, cast


class IntentClassifier(Protocol):
    def classify(self, text: str, *, available_npcs: list[str] | None = None,
                 available_targets: list[str] | None = None,
                 active_dialogue_target: str | None = None) -> dict[str, Any] | None: ...


class KeywordIntentClassifier:
    def classify(self, text: str, *, available_npcs: list[str] | None = None,
                 available_targets: list[str] | None = None,
                 active_dialogue_target: str | None = None) -> dict[str, Any] | None:
        from core.llm.dm import _classify_keywords
        return cast(dict[str, Any] | None, _classify_keywords(text, available_npcs=available_npcs,
                                  available_targets=available_targets,
                                  active_dialogue_target=active_dialogue_target))


_default_classifier: IntentClassifier = KeywordIntentClassifier()


def get_intent_classifier() -> IntentClassifier:
    return _default_classifier
