import os
import shutil
import requests
import pandas as pd
from json.decoder import JSONDecodeError
from zipfile import ZipFile
from io import BytesIO

from dgs import DATADIR

REPODICT_FILE = os.path.join(DATADIR, 'repodicts.csv')
if not os.path.isfile(REPODICT_FILE):
    open(REPODICT_FILE, 'a').close()

HEADERS = {'User-Agent': 'metagov'}


def assert_api_rate_limit_not_exceeded(r):
    try:
        assert 'API rate limit exceeded' not in r.json()['message'], 'API rate limit exceeded'
    except (TypeError, KeyError, JSONDecodeError):
        pass    


def construct_file_url(filepath, repoDict):
    """Given a repository filepath extracted from the below methods, 
    return a (hopefully valid...) URL for the file

    Note: filepath must be from root = repository root, not full local filepath!
    """

    baseURL = repoDict['url']
    if repoDict['ref']:
        baseURL = baseURL.split('/tree')[0]
        branch = repoDict['ref']
    else:
        branch = repoDict['default_branch']
    fileURL = baseURL + f'/blob/{branch}/' + filepath
    
    return fileURL
        

def get_github_api_info(githubURL):
    """Get relevant info from the URL string itself and from an API request
    
    Returns repoDict: dictionary containing repository owner, name, ref, ...
    """
    
    # Separate original URL into components
    components = githubURL.split('/')
    domainIndex = [i for (i, s) in enumerate(components) if 'github.com' in s][0]
    repoOwner = components[domainIndex+1]
    repoName = components[domainIndex+2]
    if domainIndex+2 != len(components) - 1:
        ref = components[-1]
    else:
        ref = ''
    
    # For reference, get the date that the repository was most recently updated
    apiURL = f"https://api.github.com/repos/{repoOwner}/{repoName}"
    r = requests.get(apiURL)
    assert_api_rate_limit_not_exceeded(r)
    r_base = r.json()
    defaultBranch = r_base.get('default_branch', 'master') # May be main tho!
    dateUpdated = ''
    if ref:
        # If version/tag specified
        apiURL = apiURL + '/commits/' + ref
        r = requests.get(apiURL)
        assert_api_rate_limit_not_exceeded(r)
        r_ref = r.json()
        dateUpdated = r_ref.get('commit', {}).get('committer', {}).get('date', '')
    else:
        # If main/master
        dateUpdated = r_base.get('updated_at')   

    # Define metadata
    repoDict = {'owner': repoOwner,
                'name': repoName,
                'default_branch': defaultBranch,
                'ref': ref,
                'updated_at': dateUpdated,
                'url': githubURL,
                'id': f"{repoOwner}_{repoName}" + (f"_{ref}" if ref else f"_{defaultBranch}")
                }
    
    return repoDict


def get_zipball_api_url(repoDict):
    """Given repository information, construct url for zipball
    
    Returns zipball URL, for specific version of repo if specified
    """
    
    # Construct zip URL
    zipURL = f"https://api.github.com/repos/{repoDict['owner']}/{repoDict['name']}/zipball"
    if repoDict['ref']:
        zipURL = zipURL + '/' + repoDict['ref']
    
    return zipURL
    

def download_repo(githubURL, subdir='contracts', ext='.sol'):
    """Download a specific type of file in a specific subdirectory from a GitHub repository zip file
    
    Arguments:
    - githubURL: valid GitHub URL to repository root (main or a specific version)
    - subdir: specific subdirectory (-ies) to extract content from. Can also be ''
    - ext: specific file extension to keep items from. Can also be '' 
    
    Returns:
    - repoDir: path to local directory
    - repoDict: see get_github_api_info
    
    NOTE: for ease of use with current repo structures of interest, subdir 
    matches ANY subdirectory that includes this folder name
    """

    assert 'github.com' in githubURL, "Download a repository from github.com only"
    if ext is None:
        ext = ''    
    
    repoDir = ''
    
    # Read repo API info if previously collected
    # (To prevent unnecessary API calls)
    try:
        repoDicts = pd.read_csv(REPODICT_FILE, index_col=False)
        repoDicts.fillna('', inplace=True)
        entries = repoDicts.loc[repoDicts['url'] == githubURL]
        if len(entries.index) > 0:
            repoDict = entries.iloc[0].to_dict()
        else:
            repoDict = {}
    except (FileNotFoundError, pd.errors.EmptyDataError):
        repoDict = {}
    
    try:
        # Get and save API info if not yet collected
        if repoDict == {}:
            repoDict = get_github_api_info(githubURL)
            with open(REPODICT_FILE, 'a') as f:
                if os.stat(REPODICT_FILE).st_size == 0:
                    f.write(','.join(repoDict.keys()))
                f.write('\n' + ','.join(repoDict.values()))
    
        # If target directory does not yet exist, or if subdir is not in it, download and extract
        # (To prevent unnecessary API calls; Does not overwrite existing files!)        
        targetName = repoDict['id']
        repoDir = os.path.join(TMPDIR, targetName)
        downloadFlag = False
        if not(os.path.isdir(repoDir)):
            downloadFlag = True
        else:
            foundSubdir = False
            for r, d, f in os.walk(repoDir):
                if (r == subdir) or (subdir in d):
                    foundSubdir = True
            if foundSubdir == False:
                downloadFlag = True
        
        if downloadFlag:
            # Get zip file
            zipURL = get_zipball_api_url(repoDict)
            r = requests.get(zipURL)
            assert_api_rate_limit_not_exceeded(r)
            zipFile = ZipFile(BytesIO(r.content))
            
            # Extract just the relevant subdirectory(-ies) from the zip file
            zipItems = zipFile.infolist()
            baseItem = zipItems[0].filename
            itemCount = 0
            if subdir:
                baseItem = baseItem + subdir.strip('/') + '/'
            for zi in zipItems:
                item = zi.filename
                if (f"/{subdir.strip('/')}/" in item) and item.endswith(ext):
                    zipFile.extract(item, TMPDIR)
                    itemCount += 1
            
            # Rename directory to {owner}_{name}
            oldName = baseItem.split('/')[0]
            repoDir_old = os.path.join(TMPDIR, oldName)
            if os.path.isdir(repoDir):
                print(f"Overwriting existing repository {repoDir}...")
                shutil.rmtree(repoDir)
            os.rename(repoDir_old, repoDir)
            
            print(f"Extracted {itemCount} items from {githubURL} to {repoDir}")
        else:
            print(f"Using files already in {repoDir}")

    except Exception as e: 
        print(e)
        repoDir = ''

    return repoDir, repoDict

    
if __name__ == "__main__":
    # Test with content in this repository
    testURL = 'https://github.com/notchia/dao-governance-surfaces'
    subdir = 'data/contracts'
    repoDir, repoDict = download_repo(testURL, subdir=subdir)
    assert os.path.isdir(repoDir), "could not download/unzip file as specified"
    print(f"Successfully downloaded content from {testURL}")
