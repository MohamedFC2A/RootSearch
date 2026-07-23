import os
import sys

# Re-export root config.py symbols when 'from config import config, proxy_config' is used
try:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_py_path = os.path.join(root_dir, "config.py")
    if os.path.exists(config_py_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("root_config_module", config_py_path)
        if spec and spec.loader:
            root_config_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(root_config_mod)
            config = getattr(root_config_mod, "config", None)
            proxy_config = getattr(root_config_mod, "proxy_config", None)
            SearchConfig = getattr(root_config_mod, "SearchConfig", None)
            ProxyConfig = getattr(root_config_mod, "ProxyConfig", None)
except Exception:
    pass

# Also support config.settings sub-package
try:
    from config.settings import settings, Settings
except ImportError:
    pass
