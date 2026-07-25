import sys
import os
sys.path.append('.')
from src.modules.project.services import execution_service

print("Execution File Path:", execution_service.__file__)
print("Current CWD:", os.getcwd())

with open(execution_service.__file__, 'r', encoding='utf-8') as f:
    content = f.read()
    # Check for the NEW line format in the code actually on disk at this path
    if "rendered_path" in content and "log_status" in content:
        print("DISK CHECK: Found NEW code format.")
    else:
        print("DISK CHECK: Found OLD code format.")

import inspect
source = inspect.getsource(execution_service.stream_run_suite)
if "rendered_path" in source:
    print("RUNTIME CHECK: Found NEW code in memory.")
else:
    print("RUNTIME CHECK: Found OLD code in memory.")
