import os
import sys

# Ensure current repo path takes precedence for imports
cwd = os.path.abspath(os.getcwd())
if cwd not in sys.path:
    sys.path.insert(0, cwd)

# Evict any pre-imported external 'production_system' packages
for mod in list(sys.modules.keys()):
    if mod == "production_system" or mod.startswith("production_system."):
        sys.modules.pop(mod, None)
