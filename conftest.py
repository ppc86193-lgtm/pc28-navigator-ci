import importlib.util
import os
import sys
from types import ModuleType

# Ensure repo root is first on sys.path
ROOT = os.path.abspath(os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Proactively load local production_system to avoid external package conflicts
pkg_dir = os.path.join(ROOT, "production_system")
pkg_init = os.path.join(pkg_dir, "__init__.py")
modules_py = os.path.join(pkg_dir, "modules.py")

if os.path.isdir(pkg_dir) and os.path.isfile(pkg_init):
    # Create a real package module with search locations
    spec = importlib.util.spec_from_file_location(
        "production_system", pkg_init, submodule_search_locations=[pkg_dir]
    )
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["production_system"] = mod  # register before exec for subimports
        spec.loader.exec_module(mod)  # type: ignore[arg-type]

        # Also bind production_system.modules to the local file explicitly
        if os.path.isfile(modules_py):
            sub_spec = importlib.util.spec_from_file_location(
                "production_system.modules", modules_py
            )
            if sub_spec and sub_spec.loader:
                sub_mod: ModuleType = importlib.util.module_from_spec(sub_spec)
                sys.modules["production_system.modules"] = sub_mod
                sub_spec.loader.exec_module(sub_mod)  # type: ignore[arg-type]

