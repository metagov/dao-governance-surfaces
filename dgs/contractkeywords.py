import pandas as pd

# =============================================================================
# Basic coding based on keyword searching
# =============================================================================
CODING = {
    'proposal': {'keywords': ['Proposal', 'Propose'],
                 'topics': ['create', 'modify', 'execute', 'extend', 'cancel']}, 
    'membership': {'keywords': ['Member', 'Role'],
                   'topics': ['permission', 'responsibility', 'right', 'allow', 'require', 'forbid', 'authorize']},
    'voting': {'keywords': ['Vote', 'Voting', 'Ballot'],
              'topics': ['cast', 'delegate', 'change', 'tally', 'compute', 'referendum']} ,
    'dispute_resolution': {'keywords': ['Dispute', 'Adjudication', 'Arbitrator'],
                           'topics': ['juror', 'jury', 'evidence', 'ruling', 'appeal',
                                      'create', 'compute', 'execute', 'reward', 'penalty', 'sortition']},
    'reputation': {'keywords': ['Reputation'],
                   'topics': ['reward', 'penalty', 'penalize']},
    'election': {'keywords': ['Elect', 'Candidate'],
                 'topics': ['']}
}


def find_keywords_in_str(s, camelCase=False):
    """Return list of coding keys in string s
    
    Keywords are capitalized
    """
    
    if s:
        if camelCase:
            kw = [c for c in CODING.keys() if any([(k in s) for k in CODING[c]['keywords']])]
            kw = kw + [c for c in CODING.keys() if any([(s.strip('_').lower().startswith(k.lower())) for k in CODING[c]['keywords']])]
        else:
            kw = [c for c in CODING.keys() if any([(k.lower() in s.lower()) for k in CODING[c]['keywords']])]
    else:
        kw = []

    return kw


def find_topics_in_str(s, kw, camelCase=False):
    """Return list of topics under the keyword 'kw' in string s
    
    Keywords are capitalized
    """
    
    if s:
        if camelCase:
            topics = [t for t in CODING[kw]['topics'] if (t in s)]
            topics = topics + [t for t in CODING[kw]['topics'] if (s.strip('_').lower().startswith(t.lower()))]
        else:
            topics = [t for t in CODING[kw]['topics'] if (t.lower() in s.lower())]
    else:
        topics = []

    return topics


def find_keywords_in_obj(obj, df_params):
    """Return list of coding keys in an object's name or description"""
    
    kw_name = find_keywords_in_str(obj['object_name'], camelCase=True)
    kw_description = find_keywords_in_str(obj['description'])

    kw_params = []    
    try:
        params = df_params.loc[df_params['object_name'] == obj['object_name']]
        for i, param in params.iterrows():
            kw_params = kw_params + find_keywords_in_str(param['parameter_name'], camelCase=True)
            kw_params = kw_params + find_keywords_in_str(param['description'])
    except KeyError as e:
        pass # TODO: Works okay (skips over case of no params) but there is something funny here... revisit
    
    return list(set(kw_name + kw_description + kw_params))


def find_topics_in_obj(obj, df_params):
    """Return list of topics in an object's name or description"""
    
    keywords = obj['coding_keyword_search']
    topics = []
    for kw in keywords:
        t_name = find_topics_in_str(obj['object_name'], kw=kw, camelCase=True)
        t_description = find_topics_in_str(obj['description'], kw=kw)

        t_params = []
        try:
            params = df_params.loc[df_params['object_name'] == obj['object_name']]
            for i, param in params.iterrows():
                t_params = t_params + find_topics_in_str(param['parameter_name'], kw=kw, camelCase=True)
                t_params = t_params + find_topics_in_str(param['description'], kw=kw)
        except KeyError:
            pass

        topics = topics + list(set(t_name + t_description + t_params))  
    
    return topics