import os
import shutil
import requests
import pandas as pd
from json.decoder import JSONDecodeError
from zipfile import ZipFile
from io import BytesIO
from pprint import pprint

from dgs import REPO_CONFIG_FILE, SAVEDIR


HEADERS = {'User-Agent': 'metagov'}


def assert_api_rate_limit_not_exceeded(r):
    try:
        assert 'API rate limit exceeded' not in r.json()['message'], 'WARNING: API rate limit exceeded'
    except (TypeError, KeyError, JSONDecodeError):
        pass    


def construct_file_url(filepath, repoMetadata):
    """Given a repository filepath extracted from the below methods, 
    return a (hopefully valid...) URL for the file

    Note: filepath must be from root = repository root, not full local filepath!
    """

    baseURL = repoMetadata['url']
    if repoMetadata['ref']:
        baseURL = baseURL.split('/tree')[0]
        branch = repoMetadata['ref']
    else:
        branch = repoMetadata['default_branch']
    fileURL = baseURL + f'/blob/{branch}/' + filepath
    
    return fileURL
        

def get_github_repo_metadata(githubURL):
    """Get relevant info from the URL string itself and from an API request
    
    Returns repoMetadata: dictionary containing repository owner, name, ref, ...
    """
    
    # Separate original URL into components
    components = githubURL.strip('/').split('/')
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
    defaultBranch = r_base.get('default_branch', r_base.get('master', 'main')) 
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
    repoMetadata = {
        'owner': repoOwner,
        'name': repoName,
        'default_branch': defaultBranch,
        'ref': ref,
        'updated_at': dateUpdated,
        'url': githubURL,
        'id': f"{repoOwner}_{repoName}" + (f"_{ref}" if ref else f"_{defaultBranch}")
    }
    
    return repoMetadata


def get_zipball_api_url(repoMetadata):
    """Given repository information, construct url for zipball
    
    Returns zipball URL, for specific version of repo if specified
    """
    
    version = repoMetadata['ref'] if repoMetadata['ref'] else repoMetadata['defaultBranch']

    zipURL = f"https://github.com/{repoMetadata['owner']}/{repoMetadata['name']}/zipball/{version}"

    print(zipURL)
    
    return zipURL
    

def download_repo(githubURL: str, subdir: str = 'contracts'):
    """Download a specific type of file in a specific subdirectory from a GitHub repository zip file
    
    Arguments:
    - githubURL: valid GitHub URL to repository root (main or a specific version)
    - subdir: specific subdirectory (-ies) to extract content from. Can also be ''
    
    Returns:
    - repoDir: path to local directory
    - repoMetadata: see get_github_repo_metadata
    
    NOTE: for ease of use with current repo structures of interest, subdir 
    matches ANY subdirectory that includes this folder name
    """

    assert 'github.com' in githubURL, "Download a repository from github.com only"
    FILE_EXT = '.sol'  
    
    repoDir = ''
    
    # Read repo API info if previously collected
    # (To prevent unnecessary API calls)
    try:
        repoConfigs = pd.read_csv(REPO_CONFIG_FILE, index_col=False)
        repoConfigs.fillna('', inplace=True)
        entries = repoConfigs.loc[repoConfigs['url'] == githubURL]
        if len(entries.index) > 0:
            repoMetadata = entries.iloc[0].to_dict()
        else:
            repoMetadata = {}
    except (FileNotFoundError, pd.errors.EmptyDataError):
        repoMetadata = {}
    
    try:
        # Get and save API info if not yet collected
        if repoMetadata == {}:
            print("getting metadata from api and saving to repodicts.csv")
            repoMetadata = get_github_repo_metadata(githubURL)
            with open(REPO_CONFIG_FILE, 'a') as f:
                if os.stat(REPO_CONFIG_FILE).st_size == 0:
                    f.write(','.join(repoMetadata.keys()))
                f.write('\n' + ','.join(repoMetadata.values()))
        else:
            print("using metadata from repodicts.csv")
        
        pprint(repoMetadata)

        # If target directory does not yet exist, or if subdir is not in it, download and extract
        # (To prevent unnecessary API calls, does not overwrite existing files!)        
        targetName = repoMetadata['id']
        repoDir = os.path.join(SAVEDIR, targetName)
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
            print("downloading repo")

            # Get zip file
            zipURL = get_zipball_api_url(repoMetadata)
            r = requests.get(zipURL)
            assert_api_rate_limit_not_exceeded(r)
            zipFile = ZipFile(BytesIO(r.content))
            
            # Extract just the relevant subdirectory(-ies) from the zip file
            zipItems = zipFile.infolist()
            baseItem = zipItems[0].filename
            itemCount = 0
            if subdir:
                baseItem = baseItem + subdir.strip('/') + '/'
            print(subdir)
            for zi in zipItems:
                item = zi.filename
                if (f"/{subdir.strip('/')}/" in item) and item.endswith(FILE_EXT):
                    zipFile.extract(item, SAVEDIR)
                    itemCount += 1
            
            print("extracted ZIP, now need to rename")

            # Rename directory to specified repo name
            oldName = baseItem.split('/')[0]
            repoDir_old = os.path.join(SAVEDIR, oldName)
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

    return repoDir, repoMetadata

    
if __name__ == "__main__":
    # Test with content in this repository
    testURL = 'https://github.com/notchia/dao-governance-surfaces'
    subdir = 'data/contracts'
    repoDir, repoMetadata = download_repo(testURL, subdir=subdir)
    assert os.path.isdir(repoDir), "could not download/unzip file as specified"
    print(f"Successfully downloaded content from {testURL}")
