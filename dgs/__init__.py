import os
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

sys.path.append("solidity-parser")

TMPDIR = 'tmp'

if not os.path.isdir(TMPDIR):
    os.mkdir(TMPDIR)
