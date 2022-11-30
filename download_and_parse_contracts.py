import os
import re
import ast
import shutil
import argh
import pandas as pd
import logging

from metagov.githubscrape import download_repo, construct_file_url
from metagov.contractmodel import parse_contract_file

CWD = os.path.join(os.path.dirname(__file__))
TMPDIR = os.path.join(CWD, 'tmp')

# The following default values can be added to or overridden
EXCLUDE_DIRS = ['lib', 'libs', 'libraries', 'test', 'tests', 'test-helpers', 'testHelpers', 'example', 'examples', 'migration']
EXCLUDE_FILES = ['SafeMath.sol', 'lib.sol', 'Migrations.sol']
EXCLUDE_FILE_PATTERNS = [r'I?ERC\d+\.sol', r'I?EIP\d+\.sol', r'.*\.t\.sol']


def parse_repo(projectDir, repoDict, projectLabel='', useDefaults=True, clean=False,
               excludeFiles=None, includeFiles=None, excludeDirs=None, includeDirs=None):
    """Walk through contracts and parsethe relevant files
    
    Explicitly only attempts to parse .sol files"""
    
    objectsFile = os.path.join(TMPDIR, f'contract_objects_{projectLabel}.csv')
    parametersFile = os.path.join(TMPDIR, f'contract_parameters_{projectLabel}.csv')
    
    if os.path.isfile(objectsFile) and os.path.isfile(parametersFile):
        print(f"Keeping previously parsed results for {projectDir}")
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

    df_objects = pd.DataFrame()
    df_parameters = pd.DataFrame()

    logging.info(f"Walking through {projectDir}...")
    for root, dirnames, filenames in os.walk(projectDir, topdown=True):
        subdir = root.split(projectDir)[-1]
        logging.info(f"Parsing {subdir}...")
        
        # Filter dirnames
        if len(includeDirs) > 0:
            dirnames[:] = [d for d in dirnames if d in includeDirs]
        else:
            dirnames[:] = [d for d in dirnames if d not in excludeDirs]

        # Filter filenames
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
            

def load_list(s):
    try:
        l = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        l = s
    return l


def import_contracts(csv):
    df_contracts = pd.read_csv(csv)
    df_contracts.fillna('', inplace=True)
    df_contracts.drop(columns=['url', 'notes'], inplace=True)

    for col in ['excludeDirs', 'includeDirs', 'excludeFiles', 'includeFiles']:
        df_contracts[col] = df_contracts[col].apply(load_list)
    
    return df_contracts


def download_and_parse(githubURL, subdir, label='', kwargs={}):
    
    repoDir, repoDict = download_repo(githubURL, subdir=subdir)
    
    assert os.path.isdir(repoDir), "could not download/unzip file as specified"

    if label == '':
        label = repoDict['id']
    parse_repo(repoDir, repoDict, projectLabel=label, **kwargs)
    

def download_and_parse_all():
    csv = os.path.join(CWD, 'repos.csv')
    df_contracts = import_contracts(csv)
    
    for i, row in df_contracts.iterrows():
        print(f"\n============ {row['project']} ============\n")
        kwargs = {c: row[c] for c in ['excludeDirs', 'includeDirs', 'excludeFiles', 'includeFiles'] if row[c]}
        if 'includeFiles' in kwargs.keys():
            kwargs['useDefaults'] = False
        kwargs['clean'] = False
        
        try:
            download_and_parse(row['repoURL'], row['subdir'], label=row['project'], kwargs=kwargs)
        except AssertionError as e:
            print(e)


def main(url):
    download_and_parse(url, 'contracts')

    
if __name__ == '__main__':
    argh.dispatch_command(main)
        