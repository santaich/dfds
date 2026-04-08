import subprocess
import sys


def install():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])


install()
