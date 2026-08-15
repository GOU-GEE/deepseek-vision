"""配置加载测试：默认值、环境变量、.env、config.json、优先级、校验。"""

from __future__ import annotations

import json

import pytest

from deepseek_vision_mcp.config import load_config


class TestDefaults:
    def test_defaults_applied(self):
        cfg = load_config(
            env={"VISION_API_KEY": "k"}, config_path="", validate=False
        )
        assert cfg.api_key == "k"
        assert cfg.api_keys == ["k"]
        assert cfg.model == "glm-4.6v-flash"
        assert cfg.models == ["glm-4.6v-flash"]
        assert cfg.base_url == "https://open.bigmodel.cn/api/paas/v4"
        assert cfg.max_image_size_kb == 2048
        assert cfg.timeout_seconds == 60
        assert cfg.download_timeout_seconds == 30
        assert cfg.temperature == 0.3
        assert cfg.allowed_formats == ["jpg", "jpeg", "png", "webp"]
        assert cfg.provider == "openai_compatible"
        assert cfg.cache_enabled is True

    def test_missing_api_key_raises_on_validate(self):
        with pytest.raises(ValueError, match="VISION_API_KEY"):
            load_config(env={}, config_path="")

    def test_validate_off_allows_missing_key(self):
        cfg = load_config(env={}, config_path="", validate=False)
        assert cfg.api_key == ""


class TestEnvOverride:
    def test_env_overrides_defaults(self):
        cfg = load_config(
            env={
                "VISION_API_KEY": "env-key",
                "VISION_MODEL": "qwen-vl-plus",
                "VISION_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "VISION_MAX_IMAGE_SIZE_KB": "1024",
                "VISION_TIMEOUT_SECONDS": "120",
            },
            config_path="",
        )
        assert cfg.api_key == "env-key"
        assert cfg.model == "qwen-vl-plus"
        assert cfg.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert cfg.max_image_size_kb == 1024
        assert cfg.timeout_seconds == 120

    def test_empty_env_value_ignored(self):
        cfg = load_config(
            env={"VISION_API_KEY": "k", "VISION_MODEL": ""}, config_path=""
        )
        assert cfg.model == "glm-4.6v-flash"

    def test_multiple_keys_and_models(self):
        cfg = load_config(
            env={
                "VISION_API_KEYS": "key-a, key-b,key-a",
                "VISION_MODEL": "primary-vl",
                "VISION_MODELS": "primary-vl,backup-vl",
            },
            config_path="",
        )
        assert cfg.api_keys == ["key-a", "key-b"]
        assert cfg.api_key == "key-a"
        assert cfg.models == ["primary-vl", "backup-vl"]

    def test_cross_provider_fallback_resolves_key_by_environment_name(self):
        cfg = load_config(
            env={
                "VISION_API_KEY": "primary-key",
                "VISION_FALLBACK_API_KEY": "fallback-key",
                "VISION_FALLBACKS_JSON": json.dumps([{
                    "id": "siliconflow",
                    "model": "backup-vl",
                    "base_url": "https://api.siliconflow.cn/v1",
                    "api_key_env": "VISION_FALLBACK_API_KEY",
                }]),
            },
            config_path="",
        )
        assert cfg.fallback_endpoints == [{
            "id": "siliconflow",
            "model": "backup-vl",
            "models": ["backup-vl"],
            "base_url": "https://api.siliconflow.cn/v1",
            "api_key": "fallback-key",
        }]
        assert cfg.max_attempts == 4

    def test_fallback_without_configured_credential_is_skipped(self):
        cfg = load_config(
            env={
                "VISION_API_KEY": "primary-key",
                "VISION_FALLBACKS_JSON": json.dumps([{
                    "id": "backup",
                    "model": "backup-vl",
                    "base_url": "https://backup.example/v1",
                    "api_key_env": "VISION_FALLBACK_API_KEY",
                }]),
            },
            config_path="",
        )
        assert cfg.fallback_endpoints == []


class TestConfigFile:
    def test_nested_config_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps(
                {
                    "vision": {
                        "api_key": "file-key",
                        "model": "Qwen/Qwen2.5-VL-7B-Instruct",
                        "base_url": "https://api.siliconflow.cn/v1",
                    }
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(env={}, config_path=cfg_file)
        assert cfg.api_key == "file-key"
        assert cfg.model == "Qwen/Qwen2.5-VL-7B-Instruct"
        assert cfg.base_url == "https://api.siliconflow.cn/v1"

    def test_flat_case_insensitive_config_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps(
                {"VISION_API_KEY": "flat-key", "Vision_Model": "glm-4v-plus"}
            ),
            encoding="utf-8",
        )
        cfg = load_config(env={}, config_path=cfg_file)
        assert cfg.api_key == "flat-key"
        assert cfg.model == "glm-4v-plus"

    def test_json_array_allowed_formats(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"vision": {"api_key": "k", "allowed_formats": ["JPG", "png"]}})
        )
        cfg = load_config(env={}, config_path=cfg_file)
        assert cfg.allowed_formats == ["jpg", "png"]

    def test_env_wins_over_config_file(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"vision": {"api_key": "file-key"}}))
        cfg = load_config(
            env={"VISION_API_KEY": "env-key", "VISION_USE_CONFIG_FILE": "true"},
            config_path=cfg_file,
        )
        assert cfg.api_key == "env-key"

    def test_single_env_key_overrides_file_key_list(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(
            json.dumps({"vision": {"api_keys": ["file-a", "file-b"]}})
        )
        cfg = load_config(env={"VISION_API_KEY": "env-key"}, config_path=cfg_file)
        assert cfg.api_keys == ["env-key"]

    def test_use_config_file_false_ignores_json(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"vision": {"api_key": "file-key"}}))
        cfg = load_config(
            env={"VISION_API_KEY": "env-key", "VISION_USE_CONFIG_FILE": "false"},
            config_path=cfg_file,
        )
        assert cfg.api_key == "env-key"


class TestDotEnv:
    def test_dotenv_loaded(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("VISION_API_KEY=dotenv-key\nVISION_MODEL=dotenv-model\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("VISION_API_KEY", raising=False)
        monkeypatch.delenv("VISION_MODEL", raising=False)
        # env=None 时会自动加载 cwd 下的 .env（load_dotenv 不覆盖已有环境变量）
        cfg = load_config(env=None, config_path="")
        assert cfg.api_key == "dotenv-key"
        assert cfg.model == "dotenv-model"
