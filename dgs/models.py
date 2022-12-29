import os
import re
import requests
import pprint
import validators
import argh
import pandas as pd
from dataclasses import dataclass, field
from typing import Any
from solidity_parser import parser

from dgs import TMPDIR
from dgs.comments import CommentParser
from dgs.keywords import find_keywords_in_obj, find_topics_in_obj

ERRORMSG = 'error: could not parse'
IGNORE_CONTRACTS = ['SafeMath']


# =============================================================================
# Define data model based on solidity_parser AST
# =============================================================================
@dataclass
class ContractObject():
    SUPPORTED_OBJECT_TYPES = ['ContractDefinition', 'EventDefinition', 'ModifierDefinition', 'FunctionDefinition', 'StructDefinition', 'EnumDefinition']
    NONAME_FUNC = '(none)' # For nameless delegator functions

    id: str = field(init=False)
    contract: str
    object_type: str
    object_name: str
    line_numbers: tuple
    inheritance: list[str] = field(default_factory=list) # Applicable for ContractDefinitions
    modifiers: list[str] = field(default_factory=list) # Applicable for FunctionDefinitions
    values: list[str] = field(default_factory=list) # Applicable for EnumDefinitions (?)
    visibility: str = field(default='') # Not always specified
    description: str = field(default='') # Determined using comment parsing

    parameters: list = field(default_factory=list) # Added to during ContractParameter initialization

    def __post_init__(self):
        """Create probably-unique identifier"""
        self.id = f"{self.contract}.{self.object_name}@{self.line_numbers[0]}" # TODO: hash this, and include either URL or a random string

    @classmethod
    def from_ast_node(cls, ast_node, contractName):
        """Use node of AST tree and the name of the contract"""
        
        vars = {}

        vars['contract'] = contractName
        object_type = ast_node['type']
        vars['object_type'] = object_type
        
        assert object_type in cls.SUPPORTED_OBJECT_TYPES, "{object_type} type in {contractName} is not supported by ContractObject"
        
        if object_type == 'ContractDefinition':
            vars['object_name'] = contractName
            vars['inheritance'] = [b['baseName']['namePath'] for b in ast_node.get('baseContracts', [])]
        else:
            name = ast_node['name'] 
            vars['object_name'] = name if not name.startswith('function()') else cls.NONAME_FUNC # Handle nameless delegator functions
            vars['modifiers'] = cls.get_object_modifiers(ast_node)
            vars['values'] = cls.get_object_values(ast_node)
            vars['visibility'] = ast_node.get('visibility', '')
            
        vars['line_numbers'] = (ast_node['loc']['start']['line'], ast_node['loc']['end']['line'])

        return cls(**vars)
    
    @classmethod
    def get_object_modifiers(cls, ast_node):
        """Get object modifiers"""

        modifiers = ast_node.get('modifiers', [])
        modifiers = [m.get('name', ERRORMSG) for m in modifiers]

        return modifiers

    @classmethod
    def get_object_values(cls, ast_node):
        """Get object options ("members" as defined in enum objects only)"""

        values = []

        if ast_node['type'] == 'EnumDefinition':
            members = ast_node.get('members', [])
            values = [m.get('name', ERRORMSG) for m in members]

        return values

    def add_parameter(self, paramObj):
        self.parameters.append(paramObj)

    def to_row(self):
        """Return variables as pd.Series"""
        
        objDict = {'object_name': self.object_name, 
                   'contract': self.contract, 
                   'type': self.object_type, 
                   'inheritance': self.inheritance, 
                   'modifiers': self.modifiers, 
                   'values': self.values, 
                   'visibility': self.visibility, 
                   'line_numbers': self.line_numbers, 
                   'description': self.description
                  }
        return pd.Series(objDict).to_frame().T

    def __str__(self):
        return f"{self.object_type} {self.object_name} ({self.contract})"
    

@dataclass
class ContractParameter():

    id: str = field(init=False)
    parameter_name: str
    parent_object: ContractObject
    line_number: int
    visibility: str = field(default='') # Not always specified
    parameter_type: str = field(default='') # Determined using class method
    type_category: str = field(default='') # Determined using class method
    initial_value: Any = field(default=None)  # Determined using class method
    description: str = field(default='') # Determined using comment parsing

    def __post_init__(self):
        self.id = f"{self.parent_object.contract}.{self.parent_object.object_name}.{self.parameter_name}@{self.line_number}" # TODO: hash this, and include either URL or a random string
        self.parent_object.add_parameter(self)

    @classmethod
    def from_ast_node(cls, ast_node, parent_object):
        """Initialize parameter given portion of AST tree"""
        
        vars = {}

        vars['parameter_name'] = ast_node['name']
        vars['parent_object'] = parent_object

        vars['line_number'] = ast_node['loc']['start']['line']
        vars['visibility'] = ast_node.get('visibility', '')        
        
        vars['parameter_type'] = cls.get_parameter_type(ast_node)
        vars['type_category'] = cls.get_parameter_type_category(ast_node)
        vars['initial_value'] = cls.get_parameter_initial_value(ast_node)
        
        return cls(**vars)
    
    @classmethod
    def get_parameter_type(cls, param):
        """Get parameter data type"""

        typeDict = param['typeName']
        typeType = typeDict.get('type')

        if typeType == 'Mapping':
            # Really should be something recursive to handle cases like `mapping (key => type:Mapping)`
            kType = typeDict['keyType']
            vType = typeDict['valueType']
            k = kType.get('name', kType.get('namePath', 'type:' + kType.get('type', '?')))
            v = vType.get('name', vType.get('namePath', 'type:' + vType.get('type', '?')))
            paramType = f"mapping ({k} => {v})" 
        elif typeType == 'ArrayTypeName':
            # Really should be something recursive to handle cases like `type:UserDefinedType[] memory`
            bType = typeDict.get('baseTypeName', {})
            baseType = bType.get('name', bType.get('namePath', 'type:' + bType.get('type', '?')))
            location = param.get('storageLocation', None)
            if location is None:
                location = ''
            length = typeDict.get('length', None)
            if length is None:
                length = ''
            paramType = f"{baseType}[{length}] {location}".strip()
        else:
            paramType = typeDict.get('name', typeDict.get('namePath', ERRORMSG))

        return paramType
    
    @classmethod
    def get_parameter_initial_value(cls, ast_node):
        """Get parameter initial_value"""

        value = ast_node.get('initial_value')
        if value is not None:
            value = value.get('value', str(value))

        return value
    
    @classmethod
    def get_parameter_type_category(cls, ast_node):
        """Get category of parameter dtype
        
        If ElementaryTypeName: returns the type stripped of any specific size indication (e.g., 'uint8' --> 'uint')
        If Mapping: returns 'map'
        If ArrayTypeName or UserDefinedTypeName: returns 'array' or 'userdefined'
        """

        typeDict = ast_node['typeName']
        typeType = typeDict.get('type')
        if 'TypeName' in typeType and not 'Elementary' in typeType:
            paramCategory = typeType[:-8].lower()
        elif typeType == 'Mapping':
            paramCategory = 'map'
        else:
            paramCategory = typeDict.get('name', typeDict.get('namePath', ERRORMSG))

        # Strip digits from (end of) string (to remove size spcification from bytes, int, uint8)
        paramCategory = re.sub(r"\d+", "", paramCategory)

        return paramCategory

    def to_row(self):
        """Return variables as pd.Series"""
        
        paramDict = {'parameter_name': self.parameter_name, 
                     'object_name': self.parent_object.object_name, # TODO: convert to object id and update corresponding use
                     'contract': self.parent_object.contract, 
                     'type': self.parameter_type, 
                     'type_category': self.type_category, 
                     'line_number': self.line_number, 
                     'initial_value': self.initial_value, 
                     'visibility': self.visibility, 
                     'description': self.description
                    }
        return pd.Series(paramDict).to_frame().T

    def __str__(self):
        return f"{self.parameter_name}: (parameter of {str(self.parent_object)})"


# =============================================================================
# Populate data model based on solidity_parser AST
# =============================================================================    
def extract_objects_and_parameters(sourceUnit):
    """Collect information on contract objects and their parameters
    
    Input: solidity-parser parsed AST for the contract file
    
    Returns two DataFrames:
      - df_objects contains contracts, function, event, modifier, struct, and enum definitions
      - df_parameters contains state variables, function arguments, struct values, and other
        parameters needed to define or call the above
        
    Each contract/parameter is first defined using the ContractObject or ContractParameter class
    to pull the relevant information from the AST node, then exported to a Series for storage in
    the corresponding DataFrame.
    """
    
    # Get list of relevant contract nodes defined in Solidity file
    contracts = [c for c in sourceUnit['children'] if c.get('type') == 'ContractDefinition']
    contracts = [c for c in contracts if c['name'] not in IGNORE_CONTRACTS]
    
    df_objects = pd.DataFrame()
    df_parameters = pd.DataFrame()
    
    # Iterate through contracts to extract objects and their parameters
    for c in contracts:
        contractName = c['name']
    
        # Append object for the contract itself
        contract = ContractObject.from_ast_node(c, contractName)
        df_objects = pd.concat([df_objects, contract.to_row()], ignore_index=True)

        # Iterate through relevant subnodes in contract
        for item in c.get('subNodes', []):
            itemType = item['type']
            
            if itemType == 'StateVariableDeclaration':
                # Append contract state variables to parameters DataFrame
                for param in item.get('variables', {}):
                    stateVar = ContractParameter.from_ast_node(param, contract)
                    df_parameters = pd.concat([df_parameters, stateVar.to_row()], ignore_index=True)
            else:
                try: 
                    # Append function/event/modifier definition to objects DataFrame
                    contractObj = ContractObject.from_ast_node(item, contractName)
                    df_objects = pd.concat([df_objects, contractObj.to_row()], ignore_index=True)

                    # Append each parameter to DataFrame
                    paramObj = item.get('parameters', (item.get('members', {})))
                    if isinstance(paramObj, dict):
                        values = paramObj.get('parameters', [])
                    elif isinstance(paramObj, list) and itemType == 'StructDefinition':
                        values = paramObj
                    else:
                        values = []
                    for param in values:
                        contractParam = ContractParameter.from_ast_node(param, contractObj)
                        df_parameters = pd.concat([df_parameters, contractParam.to_row()], ignore_index=True)
                except AssertionError as e:
                    # If unsupported object type is encountered
                    pass

    return df_objects, df_parameters


# =============================================================================
# Main function
# =============================================================================
def parse_contract_file(uri, debug=False):
    """Parse a Solidity contract file from a filepath or a URL
    
    If present, prepend 'label' to parsed AST filename for easier batch parsing
    
    returns df_objects, df_parameters
    """
    
    assert (validators.url(uri) == True or os.path.isfile(uri)), 'supply a valid file path or URL'
    
    if validators.url(uri) == True:
        # Download content of file from URL 
        content = requests.get(uri).text
        fpath = os.path.join(TMPDIR, 'solidity.txt')
        with open(fpath, 'w') as f:
            f.write(content)
        lines = content.split('\n')
        saveName = uri.split('/')[-1].split('.')[0]
    else:
        # Open existing file
        fpath = uri
        with open(fpath, 'r') as f:
            lines = f.readlines()
        saveName = os.path.splitext(os.path.split(uri)[-1])[0]

    # Get file structure as OrderedList and split into contracts
    sourceUnit = parser.parse_file(fpath, loc=True)
    
    # Save AST to file for debugging
    if debug:
        with open(os.path.join(TMPDIR, f'parsed_{saveName}.txt'), 'w') as f:
            pprint.pprint(sourceUnit, stream=f)    
    
    # Get object and parameter DataFrames (selecting from solidity_parser AST)
    df_objects, df_parameters = extract_objects_and_parameters(sourceUnit)
    
    # Add comments to the DataFrames
    cp = CommentParser()
    df_objects, df_parameters = cp.add_docstring_comments(lines, df_objects, df_parameters)
    df_parameters = cp.add_inline_comments(lines, df_parameters)
    df_parameters = cp.remove_duplicate_comments_in_parameters(df_objects, df_parameters)

    # Add coding keywords/topics to the DataFrames
    df_objects['coding_keyword_search'] = df_objects.apply(lambda row: find_keywords_in_obj(row, df_parameters), axis=1)
    df_objects['coding_topic_search'] = df_objects.apply(lambda row: find_topics_in_obj(row, df_parameters), axis=1)  
    
    return df_objects, df_parameters


if __name__ == "__main__":
    argh.dispatch_command(parse_contract_file)