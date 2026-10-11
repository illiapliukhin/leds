"""Write ledsim/_build.py with the git SHA of the checkout and the build time (shown in the window title + status bar)."""
import os, subprocess, datetime
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sha = subprocess.run(['git', '-C', APP, 'rev-parse', '--short=7', 'HEAD'], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(['git', '-C', APP, 'status', '--porcelain', '--', '.'], capture_output=True, text=True).stdout.strip()
now = datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
open(os.path.join(APP, 'ledsim', '_build.py'), 'w').write("GIT_SHA = %r\nBUILD_TIME = %r\n" % (sha + ('+dirty' if dirty else ''), now))
print(sha, now, 'dirty' if dirty else 'clean')
