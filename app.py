"""
Opsolutely Autodeployer

This app is a simple webservice that, when you GET /_status, will make
new git commits to itself and then push them to GitHub.
The commit only happens if the app has been booted for at least a
minute. If this app is automatically deployed on every git commit to
master then it functions as a self-deploying application.

Once the app has been up for ten minutes the /_status endpoint begins to
return HTTP 500 responses

Deploys, like unit tests, should never take ten minutes.

"""
import subprocess
import json
import os
from time import time
from flask import Flask

process = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
sha = process.communicate()[0].replace(b'\n', b'').decode('utf-8')
whoami = os.popen('whoami').read().replace('\n', '')
boot_time = time()
private_key_location = "/{}/.ssh/id_rsa".format(whoami)

app = Flask(__name__)
app.new_commit_added = False

"""
First we make sure we have the right RSA private key to push new commits
to GitHub
"""
try:
    os.open(private_key_location, os.O_RDONLY)
except FileNotFoundError:
    # We're in an environment with no private key set. We expect there
    # is one in the environment
    # TODO: read this secret from virtual filesystem so it's never
    # outside the process
    try:
        private_key = os.environ['PRIVATE_KEY']
    except KeyError:
        print("""
        To run this app you need to specify a PRIVATE_KEY env variable
        containing the contents of a private RSA key that can push to GitHub

        docker run -e PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY----- ..."
        """)
        exit(1)
    # Install the env-specified private key to ~/.ssh/id_rsa
    p = subprocess.Popen([
            'install',
            '-m',
            '600',
            '/dev/stdin',
            private_key_location,
        ], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
    p.communicate(input=private_key.encode('utf-8'))


@app.route('/_status')
def version():
    maybe_add_commit()
    return json.dumps({
            'sha': sha,
            'deploy_time': boot_time,
        })


@app.route('/')
def root():
    return '<h2>Current Autodeployer version: {}</h2>'.format(sha)


def maybe_add_commit():
    """
    If the app has been booted for at least a minute then make a new git
    commit, then no longer attempt this function for the life of the
    process.
    """
    if app.new_commit_added:
        return
    if boot_time + 60 < time():
        add_commit()
        app.new_commit_added = True


def add_commit():
    message = "{} - FROM {} in {}".format(
            time(),
            os.environ.get('COMMIT_HASH'),
            os.environ.get('ENVIRONMENT'))

    subprocess.Popen(["git", "commit", "--allow-empty", "-m", message], stdout=subprocess.PIPE)
    subprocess.Popen(["git", "push", "origin", "master"], stdout=subprocess.PIPE)
