import pytest
import os

from dgs.github import download_repo

def test_download_repo():
    """Test with data in this repository"""

    testURL = 'https://github.com/notchia/dao-governance-surfaces'
    subdir = 'tests/data/Compound'
    repoDir, repoMetadata = download_repo(testURL, subdir=subdir)

    assert repoMetadata.get('owner') == 'notchia'
    assert repoMetadata.get('name') == 'dao-governance-surfaces'
    assert os.path.isdir(repoDir), "could not download/unzip file as specified"
    assert len(os.listdir(repoDir)), "files are missing"