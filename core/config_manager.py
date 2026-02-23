import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    """全局配置管理器 (单例模式)"""
    
    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False
    
    # 兼容 PyInstaller 打包后的路径
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
    else:
        BASE_DIR = Path(__file__).parent.parent
    
    CONFIG_PATH: Path = BASE_DIR / "data" / "global_config.json"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.config: Dict[str, Any] = self._load_config()
        self._initialized = True

    def _load_config(self) -> Dict[str, Any]:
        """从本地加载配置文件"""
        if not self.CONFIG_PATH.exists():
            return {"user_role": None}
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"user_role": None}

    def save_config(self) -> None:
        """保存配置到本地文件"""
        try:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.save_config()

    def get_role(self) -> Optional[str]:
        return self.get("user_role")

    def set_role(self, role: Optional[str]) -> None:
        self.set("user_role", role)