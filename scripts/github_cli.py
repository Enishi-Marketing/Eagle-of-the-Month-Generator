"""Run GitHub CLI using its login or Git's existing GitHub credential helper.

Credentials remain in memory and are never printed or saved in the project.
"""
import os
import shutil
import subprocess
import sys

gh = shutil.which('gh') or '/opt/homebrew/bin/gh'
environment = os.environ.copy()
if not environment.get('GH_TOKEN') and subprocess.run(
    [gh, 'auth', 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
).returncode:
    helper_env = dict(environment, GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(
        ['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n\n',
        text=True, capture_output=True, env=helper_env, timeout=30
    )
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = fields.get('password')
    if not token:
        raise SystemExit('GitHub authentication required. Run gh auth login.')
    environment['GH_TOKEN'] = token
raise SystemExit(subprocess.run([gh, *sys.argv[1:]], env=environment).returncode)
