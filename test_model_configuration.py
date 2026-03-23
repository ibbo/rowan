#!/usr/bin/env python3
"""
Tests for model list and default model configuration.
"""

import ast
from pathlib import Path

import settings


ROOT = Path(__file__).parent


def _parse_module(path: str) -> ast.AST:
    return ast.parse((ROOT / path).read_text())


def _get_function_arg_default(module: ast.AST, function_name: str, arg_name: str) -> str:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            args = node.args.args
            defaults = node.args.defaults
            offset = len(args) - len(defaults)
            for index, arg in enumerate(args):
                if arg.arg == arg_name:
                    default = defaults[index - offset]
                    return ast.literal_eval(default)
    raise AssertionError(f"Could not find default for {function_name}.{arg_name}")


def _get_method_arg_default(module: ast.AST, class_name: str, method_name: str, arg_name: str) -> str:
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    args = item.args.args
                    defaults = item.args.defaults
                    offset = len(args) - len(defaults)
                    for index, arg in enumerate(args):
                        if arg.arg == arg_name:
                            default = defaults[index - offset]
                            return ast.literal_eval(default)
    raise AssertionError(f"Could not find default for {class_name}.{method_name}.{arg_name}")


def _get_openai_model_ids(module: ast.AST) -> list[str]:
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "OpenAIProvider":
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "MODELS":
                            models = ast.literal_eval(item.value)
                            return [model["id"] for model in models]
    raise AssertionError("Could not find OpenAIProvider.MODELS")


def test_openai_models_include_gpt_5_4_mini_first():
    """The new default OpenAI model should be offered first."""
    model_ids = _get_openai_model_ids(_parse_module("llm_providers.py"))

    assert "gpt-5.4-mini" in model_ids
    assert model_ids[0] == "gpt-5.4-mini"


def test_runtime_defaults_use_gpt_5_4_mini():
    """Core code paths should default to the new model."""
    llm_providers = _parse_module("llm_providers.py")
    scd_agent = _parse_module("scd_agent.py")
    lesson_planner = _parse_module("lesson_planner.py")

    assert _get_function_arg_default(llm_providers, "get_llm", "model") == "gpt-5.4-mini"
    assert _get_method_arg_default(scd_agent, "SCDAgent", "__init__", "model") == "gpt-5.4-mini"
    assert _get_method_arg_default(lesson_planner, "LessonPlannerAgent", "__init__", "model") == "gpt-5.4-mini"


def test_settings_default_model_is_gpt_5_4_mini(tmp_path, monkeypatch):
    """Fresh settings databases should default to the new model."""
    monkeypatch.setattr(settings, "SETTINGS_DB_PATH", str(tmp_path / "settings.db"))

    settings.init_settings_db()

    llm_settings = settings.get_llm_settings()

    assert llm_settings["provider"] == "openai"
    assert llm_settings["model"] == "gpt-5.4-mini"
    assert llm_settings["temperature"] == 0.0


def test_settings_migrate_legacy_openai_default(tmp_path, monkeypatch):
    """Existing installs on the old untouched OpenAI default should migrate once."""
    monkeypatch.setattr(settings, "SETTINGS_DB_PATH", str(tmp_path / "settings.db"))

    settings.init_settings_db()
    settings.set_setting("llm_provider", "openai")
    settings.set_setting("llm_model", "gpt-4o-mini")
    settings.set_setting("llm_defaults_version", "older-default")

    settings.init_settings_db()

    assert settings.get_llm_settings()["model"] == "gpt-5.4-mini"
