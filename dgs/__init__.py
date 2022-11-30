import os
import sys
sys.path.append("solidity-parser")

if not os.path.isdir('tmp'):
    os.mkdir('tmp')

TMPDIR = 'tmp'
DATADIR = 'data'