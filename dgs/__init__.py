import os
import sys
import json
import logging

logging.basicConfig(level=logging.DEBUG)

sys.path.append("solidity-parser")

TMPDIR = 'tmp'

if not os.path.isdir(TMPDIR):
    os.mkdir(TMPDIR)

import json

KEYWORD_CONFIG_FILE = 'config/keywords.json'
assert os.path.isfile(KEYWORD_CONFIG_FILE ), "Provide a keyword file"
with open(KEYWORD_CONFIG_FILE, 'r') as f:
    CODING = json.load(f)['categories']