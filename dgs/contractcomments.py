import re

# =============================================================================
# Populate object and parameter comments
# =============================================================================
def _clean_comment_lines(lines):
    """Clean list of strings that may contain a block comment or contiguous set of
    individual line comments.
    
    Assumes that, if the list contains multiple such blocks/sets, the only relevant one
    is the one at the end of the list (immediately prior to e.g., the object definition).
    
    Arguments:
    - lines (list(str)): list of lines that may contain comments
    Returns:
    - lines_new (list(str)): cleaned list of comments (may be empty list)
    """
    
    lines = [s.strip() for s in lines if s.strip()]
    linesStr = '\n'.join(lines)
    
    # Try to get comment block right before the object, if there is one
    pattern_commentBlock = re.compile(r'/\*\*(.+?)\*/$', re.DOTALL)
    match = re.search(pattern_commentBlock, linesStr)
    if match:
        # Remove asterisks
        lines_new = match.group(1).split('\n')
        lines_new = [re.sub('^\s*\*\s*', '', s).strip() for s in lines_new if s]
    else:
        # Otherwise, get contiguous block of individual line comments right before object
        lines_new = []
        i = len(lines) - 1
        endFlag = False
        while i >= 0 and not endFlag:
            if lines[i].startswith('//'):
                lines_new.append(re.sub(r'//+', '', lines[i]).strip())
            else:
                endFlag = True
            i -= 1
        lines_new = lines_new[::-1]
    
    return lines_new


def clean_comment_lines(lines_raw, includesInline=False):
    """Clean list of strings of up to (and including, if includesInline=True)
    an object or parameter definition
    
    Arguments:
      - lines_raw (list(str)): list of lines that may contain comments
      - includesInline (bool): whether the last entry in the list should be
        parsed as an inline comment
    Returns:
      - lines_new (list(str)): cleaned list of comments (may be empty list)
    """
    
    if includesInline:
        # Clean comment lines prior to inline
        prevLines = _clean_comment_lines(lines_raw[:-1])
        
        # Clean inline comment separately and add to prior comments
        tmp = re.split(r'//+', lines_raw[-1])
        inLine = [tmp[-1]] if len(tmp) > 1 else ['']
        lines_new = prevLines + inLine
    else:
        lines_new = _clean_comment_lines(lines_raw)
    
    lines_new = [s.strip() for s in lines_new if s.strip()]
    
    return lines_new


def parse_object_comments(lines_raw):
    """Clean and parse list of lines prior to an object definition.
    May contain a block comment or individual line comments. If it contains 
    unrelated lines of code, these will be filtered out.
    Tries to find NatSpec tags, if any; either way, keeps full comment and sets
    a one-line description.
        
    Arguments:
      - lines_raw (list(str)): list of lines that may contain relevant comments
    Returns:
      - commentDict (dict): contains the following:
          - tag:value items for any NatSpec tags used. For 'param', value is
            dict of param:description items
          - 'full_comment' and 'description' keys for full (cleaned) comment
            string and one-line description
    """

    commentDict = {}    
    
    # Clean lines
    lines = clean_comment_lines(lines_raw)  
    
    # Don't bother with the rest if no description was found
    if len(lines) == 0:
        return commentDict

    # Add full (cleaned) comment
    commentDict['full_comment'] = '\n'.join(lines)  
    
    # Add tag values, if NatSpec is used
    splitLines = re.split(r'\n@([a-z]+)', '\n' + '\n'.join(lines))[1:] 
    if len(splitLines) > 0:
        values = zip(splitLines[::2], splitLines[1::2])
        for (tag, value) in values:
            prevValue = commentDict.get(tag, '')
            if not prevValue:
                commentDict[tag] = value.replace('\n', ' ').strip()
            else:
                commentDict[tag] = prevValue + '\n' + value.replace('\n', ' ').strip()
    
    # Split parameters (if any) into a dictionary
    params = commentDict.get('param', '')
    if params:
        paramLines = [s.split(' ', 1) for s in params.split('\n')]
        commentDict['param'] = {p[0]: p[1] for p in paramLines}
    
    # Control flow for choosing main description
    if 'title' in commentDict.keys():
        description = commentDict['title']
    elif 'notice' in commentDict.keys():
        description = commentDict['notice']
    elif 'dev' in commentDict.keys():
        description = commentDict['dev']
    elif 'return' in commentDict.keys():
        description = commentDict['return']
    else:
        description = commentDict['full_comment'].split('.')[0]
    commentDict['description'] = description
    
    return commentDict


def parse_parameter_comments(lines_raw):
    """Clean and parse list of lines up to and including a parameter definition.
    May contain a block comment or individual line comments. If it contains 
    unrelated lines of code, these will be filtered out.
        
    Arguments:
      - lines_raw (list(str)): list of lines that may contain relevant comments
    Returns:
      - commentDict (dict): contains the following:
          - 'full_comment' and 'description' keys for full (cleaned) comment
            string and one-line description
    """

    # Clean lines
    lines = clean_comment_lines(lines_raw, includesInline=True)
    
    commentDict = {}

    # Don't bother with the rest if no description was found
    if len(lines) == 0:
        return commentDict    
   
    # Add full (cleaned) comment
    commentDict['full_comment'] = '\n'.join(lines)      

    # Strip any tags from the description
    lines_noTags = [re.split(r'@[a-z]+', s)[-1].strip() for s in lines]
    
    # Add description
    hasInline = (lines[-1] in lines_raw[-1])
    if hasInline and len(lines) == 1:
        inline = lines[0]
        description = inline
    elif hasInline:
        description = ' '.join(lines_noTags[:-1])
        inline = lines_noTags[-1]
    else:
        description = ' '.join(lines_noTags)
        inline = ''
    commentDict['description'] = description
    commentDict['inline_comment'] = inline
    
    return commentDict


def add_docstring_comments(lines, df_objects, df_parameters):
    """Parse comments and add them to the relevant rows in the object and parameter DataFrames"""

    df_o = df_objects.copy(deep=True)
    df_p = df_parameters.copy(deep=True)

    # Define tags to keep
    NATSPEC_TAGS = ['title', 'notice', 'dev', 'param', 'return']
    for tag in NATSPEC_TAGS:
        df_o[tag] = ''
    df_o['description'] = ''
    df_o['full_comment'] = ''
        
    prevObjectLoc = (0,0)
    for i, row in df_o.iterrows():
        # Get, clean, and parse object comment lines
        commentEnd = row['line_numbers'][0] - 1
        if prevObjectLoc[1] <= commentEnd:
            commentStart = prevObjectLoc[1]
        else:
            commentStart = prevObjectLoc[0]
        commentLines = lines[commentStart:commentEnd]
        commentDict = parse_object_comments(commentLines)

        # Add object descriptions to objects
        for key, value in commentDict.items():
            if key in df_o.columns:
                if key == 'param':
                    value = list(value.keys())
                df_o.iat[i, df_o.columns.get_loc(key)] = value               

        # Add parameter descriptions to parameters
        for paramName, paramDescription in commentDict.get('param', {}).items():
            index = df_p.loc[(df_p['object_name']==row['object_name']) &
                             (df_p['parameter_name']==paramName)].index[0]
            df_p.iat[index, df_p.columns.get_loc('description')] = paramDescription

        prevObjectLoc = row['line_numbers']

    return df_o, df_p


def add_inline_comments(lines, df_parameters):
    """Parse comments and add them to the relevant rows in the parameter DataFrame"""

    df_p = df_parameters.copy(deep=True)
    df_p['full_comment'] = ''

    commentStart = 0
    for i, row in df_p.iterrows():   
        # Grab and parse comment lines
        commentEnd = int(row['line_number'])
        commentLines = lines[min(commentStart, commentEnd - 2):commentEnd]
        commentDict = parse_parameter_comments(commentLines)
        
        # Add to dict (but don't overwrite previously found value)
        for key, value in commentDict.items():
            if key in df_p.columns:
                currentValue = df_p.iat[i, df_p.columns.get_loc(key)]
                if not currentValue:
                    df_p.iat[i, df_p.columns.get_loc(key)] = value

        commentStart = commentEnd

    return df_p


def remove_duplicate_comments_in_parameters(df_o, df_parameters):
    """Remove description and/or full comment for a parameter if it is 
    the same as its parent object's description"""
    
    df_p = df_parameters.copy(deep=True)
    
    for i, row in df_parameters.iterrows():
        # Get parent object's comments
        index = df_o.loc[(df_o['object_name']==row['object_name']) &
                         (df_o['contract']==row['contract'])].index[0]
        object_fullComment = df_o.iat[index, df_o.columns.get_loc('full_comment')]
        object_description = df_o.iat[index, df_o.columns.get_loc('description')]
        
        # Delete parameter's comment(s) if duplicate of parent object's (i.e., not parameter-specific)
        if (row['full_comment'] == object_fullComment) or ('@param' in object_fullComment):
            df_p.iat[i, df_p.columns.get_loc('full_comment')] = ''
        if row['description'] == object_description:
            df_p.iat[i, df_p.columns.get_loc('description')] = ''
        
    return df_p
