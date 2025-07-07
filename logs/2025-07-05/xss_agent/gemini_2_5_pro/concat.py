#!/usr/bin/env python3
Concatenate all *agent* logs beneath this directory.

Skips any logs inside a *full_requests* sub-directory and files whose names
end with '_requests.log'.

Usage::
    python concat.py > combined.log
import pathlib, sys

root = pathlib.Path(__file__).resolve().parent
logs = sorted(root.rglob('*.log'))
for log_path in logs:
    if 'full_requests' in log_path.parts or log_path.name.endswith('_requests.log'):
        continue
    print('=' * 80, file=sys.stdout)
    print(log_path.relative_to(root), file=sys.stdout)
    print('-' * 80, file=sys.stdout)
    sys.stdout.write(log_path.read_text())
    print('\n', file=sys.stdout)
