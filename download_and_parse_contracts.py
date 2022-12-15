import os
import re
import shutil
import argh
import pandas as pd
import logging

from dgs import TMPDIR
from dgs.github import download_repo, construct_file_url
from dgs.models import parse_contract_file
from dgs.utils import ast_eval


# The following default values can be added to or overridden
EXCLUDE_DIRS = ['lib', 'libs', 'libraries', 'test', 'tests', 'test-helpers', 'testHelpers', 'example', 'examples', 'migration']
EXCLUDE_FILES = ['SafeMath.sol', 'lib.sol', 'Migrations.sol']
EXCLUDE_FILE_PATTERNS = [r'I?ERC\d+\.sol', r'I?EIP\d+\.sol', r'.*\.t\.sol']

REPO_TABLE_PATH = 'repos.csv'


def parse_repo(projectDir, repoDict, projectLabel='', useDefaults=True, clean=False,
               excludeFiles=None, includeFiles=None, excludeDirs=None, includeDirs=None):
    """Walk through contracts and parse the relevant files
    
    Only attempts to parse .sol files
    """
    
    if projectLabel: 
        projectLabel = '_' + projectLabel

    #contractsFile = os.path.join(TMPDIR, f'contracts{projectLabel}.csv')
    objectsFile = os.path.join(TMPDIR, f'contract_objects{projectLabel}.csv')
    parametersFile = os.path.join(TMPDIR, f'contract_parameters{projectLabel}.csv')
    
    if os.path.isfile(objectsFile) and os.path.isfile(parametersFile):
        print(f"Keeping previously parsed results for {projectLabel}")
        return
    
    if excludeFiles is None:
        excludeFiles = []
    if includeFiles is None:
        includeFiles = []
    if excludeDirs is None:
        excludeDirs = []
    else:
        assert type(excludeDirs) == list, "provide excludeDirs as a list of strings"
    if includeDirs is None:
        includeDirs = []
    else:
        assert type(includeDirs) == list, "provide excludeDirs as a list of strings"
    
    assert os.path.isdir(projectDir), "specify an existing directory"
    assert not (len(excludeFiles) > 0 and len(includeFiles) > 0), "specify only files to exclude or to include, not both"
    assert not (len(excludeDirs) > 0 and len(includeDirs) > 0), "specify only subdirectory names to exclude or to include, not both"
    
    if useDefaults:
        excludeFiles += EXCLUDE_FILES
        excludeDirs += EXCLUDE_DIRS

    errorFiles = []
    fileCount = 0

    #df_contracts = pd.DataFrame()
    df_objects = pd.DataFrame()
    df_parameters = pd.DataFrame()

    logging.info(f"Walking through {projectDir}...")
    for root, dirnames, filenames in os.walk(projectDir, topdown=True):
        subdir = root.split(projectDir)[-1]
        logging.info(f"Parsing {subdir}...")
        
        # Filter directories by name
        if len(includeDirs) > 0:
            dirnames[:] = [d for d in dirnames if d in includeDirs]
        else:
            dirnames[:] = [d for d in dirnames if d not in excludeDirs]

        # Filter files by name
        if len(includeFiles) > 0:
            filenames = [f for f in filenames if f in includeFiles]
        else:
            filenames = [f for f in filenames if f.endswith('.sol')]
            filenames = [f for f in filenames if f not in excludeFiles]
            if useDefaults:
                filenames = [f for f in filenames if not any([re.match(p, f) for p in EXCLUDE_FILE_PATTERNS])]

        # Parse each file and append objects and parameters to main dfs
        for fname in filenames:
            fpath = os.path.join(root, fname)
            try:
                df_o, df_p = parse_contract_file(fpath, label=repoDict['name'])
                fileURL = construct_file_url(f"{subdir.strip('/')}/{fname}", repoDict)
                df_o['url'] = fileURL
                df_p['url'] = fileURL
                df_objects = pd.concat([df_objects, df_o])
                df_parameters = pd.concat([df_parameters, df_p])
                fileCount += 1
            except Exception as e:
                logging.exception(f"Error parsing {fname}:\n{str(e)}")
                errorFiles.append(os.path.join(subdir, fname))
        
    # Save parsed data to files
    if (len(df_objects.index) > 0):
        df_objects['project'] = projectLabel
        df_objects['repo_update_datetime'] = repoDict['updated_at']
        df_objects['repo_version'] = repoDict['ref']
        df_objects['repo_url'] = repoDict['url']
        df_objects.drop(columns=['line_numbers']).reset_index().to_csv(objectsFile)
        df_parameters.drop(columns=['line_number']).reset_index().to_csv(parametersFile)
    
    logging.info(f"Summary for {projectLabel}: parsed {fileCount} files")
    if len(errorFiles) > 0:
        logging.warning("Could not parse the following files:")
        for f in errorFiles:
            logging.warning(f"\t{f}")
            
    if clean:
        shutil.rmtree(projectDir)


def import_contracts(csv):
    """Import configuration data about which contracts to parse from local file"""

    df_contracts = pd.read_csv(csv)
    df_contracts.fillna('', inplace=True)
    df_contracts.drop(columns=['url', 'notes'], inplace=True)

    for col in ['excludeDirs', 'includeDirs', 'excludeFiles', 'includeFiles']:
        df_contracts[col] = df_contracts[col].apply(ast_eval)
    
    return df_contracts


def download_and_parse(githubURL, subdir, label='', kwargs={}):
    """Download and parse a GitHub repository from a URL"""
    
    repoDir, repoDict = download_repo(githubURL, subdir=subdir)
    assert os.path.isdir(repoDir), "could not download/unzip file as specified"

    if label == '':
        label = repoDict['id']
    parse_repo(repoDir, repoDict, projectLabel=label, **kwargs)
    

def download_and_parse_all():
    df_contracts = import_contracts(REPO_TABLE_PATH)
    
    for i, row in df_contracts.iterrows():
        print(f"\n============ {row['project']} ============\n")
        kwargs = {c: row[c] for c in ['excludeDirs', 'includeDirs', 'excludeFiles', 'includeFiles'] if row[c]}
        if 'includeFiles' in kwargs.keys():
            kwargs['useDefaults'] = False
        kwargs['clean'] = False
        
        try:
            download_and_parse(row['repoURL'], row['subdir'], label=row['project'], kwargs=kwargs)
        except AssertionError as e:
            logging.exception(e)


def main(url):
    download_and_parse(url, 'contracts')

    
if __name__ == '__main__':
    argh.dispatch_command(main)
        