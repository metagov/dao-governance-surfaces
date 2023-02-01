import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append("solidity-parser")

TMPDIR = 'tmp'
CONFIGDIR = 'config'
SAVEDIR = TMPDIR

if not os.path.isdir(TMPDIR):
    os.mkdir(TMPDIR)

REPO_CONFIG_FILE = os.path.join(CONFIGDIR, 'repodicts.csv')
if not os.path.isfile(REPO_CONFIG_FILE):
    if not os.path.isdir(CONFIGDIR):
        os.mkdir(CONFIGDIR)
    open(REPO_CONFIG_FILE, 'a').close()

KEYWORD_CONFIG_FILE = os.path.join(CONFIGDIR, 'keywords.json')
assert os.path.isfile(KEYWORD_CONFIG_FILE ), "Provide a keyword file"
with open(KEYWORD_CONFIG_FILE, 'r') as f:
    CODING = json.load(f)['categories']