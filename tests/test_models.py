import pytest
import os
from solidity_parser import parser
from pprint import pprint

from dgs import TMPDIR
from dgs.models import ContractObject, ContractParameter


REQUIRED_COLUMNS_OBJECT = ['contract', 'object_type', 'object_name', 'line_numbers', 'inheritance', 'modifiers', 'values', 'visibility', 'description']
REQUIRED_COLUMNS_PARAMETER = ['parameter_name', 'contract', 'object_name', 'line_number', 'type', 'type_category', 'initial_value', 'visibility', 'description']


@pytest.fixture()
def get_contracts_ast(request):
    """Get list of ASTs for each contract in file"""

    fname = 'GovernorBravoDelegator.sol'
    fpath = os.path.join('tests/data/Compound', fname)
    assert os.path.isfile(fpath)
    sourceUnit = parser.parse_file(fpath, loc=True)
    
    # Save AST to file for debugging
    tmppath = os.path.join(TMPDIR, f'parsed_{fname}.json')
    if not os.path.isfile(tmppath):
        with open(tmppath, 'w') as f:
            pprint(sourceUnit, stream=f)

    contracts = [c for c in sourceUnit['children'] if c.get('type') == 'ContractDefinition'][0]

    return contracts


def test_ContractObject(get_contracts_ast):
    """Test that the following runs without throwing an error"""

    # Get node corresponding to first contract
    c = get_contracts_ast[0]
    
    contractName = c['name']
    contractObj = ContractObject.from_ast_node(c, contractName)

    contractRow = contractObj.to_row()
    
    assert all([c in REQUIRED_COLUMNS_OBJECT for c in contractRow.columns])