"""
Populate object and parameter comments

TODO: rewrite add_docstring_comments and add_inline_comments to use only one column of df (takes way more memory than necessary rn)
TODO: proofread and refactor add_docstring_comments, add_inline_comments, remove_duplicate_comments_in_parameters
TODO: test everything!
"""

import re
from pandas import DataFrame


class CommentParser:
    PATTERN_SEARCH_COMMENTBLOCK = re.compile(r'/\*\*(.+?)\*/$', re.DOTALL)
    PATTERN_SUB_ASTERISKS = r'^\s*\*\s*'
    LINE_COMMENT_MARKER = '//'
    PATTERN_LINE_COMMENT = rf'{{{LINE_COMMENT_MARKER}}}+' # For re.sub or re.split


    def clean_comment_block(self, lines: list[str]) -> list[str]:
        """Clean list of strings that may contain a Solidity block comment or 
        contiguous set of individual line comments.
        
        Assumes that, if the list contains multiple such blocks/sets, the only 
        relevant one is the one at the end of the list (immediately prior to e.g., 
        the object definition).
        
        Arguments:
        - lines: list of lines that may contain comments
        Returns:
        - lines_new: cleaned list of comments (may be empty list)
        """
        
        # Drop empty lines and join by newlines
        lines = [s.strip() for s in lines if s.strip()]
        linesStr = '\n'.join(lines)
        
        # Try to get comment block right before the object, if there is one
        match = re.search(self.PATTERN_SEARCH_COMMENTBLOCK, linesStr)
        if match:
            # Remove any asterisks
            lines_new = match.group(1).split('\n')
            lines_new = [re.sub(self.PATTERN_SUB_ASTERISKS, '', s).strip() for s in lines_new if s]
        else:
            # Otherwise, iterate backwards from the last line to get the contiguous 
            # block of individual line comments right before the code line of interest
            lines_new = []
            i = len(lines) - 1
            endFlag = False
            while i >= 0 and not endFlag:
                if lines[i].startswith(self.LINE_COMMENT_MARKER):
                    lines_new.append(re.sub(rf'{{{self.LINE_COMMENT_MARKER}}}+', '', lines[i]).strip())
                else:
                    endFlag = True
                i -= 1
            lines_new = lines_new[::-1]
        
        return lines_new


    def clean_inline_comment(self, line: str) -> str:
        """Clean string that may include an inline comment after code
        
        Assumes there are no newline characters in the string

        Arguments:
        - line: string that may contain comment
        Returns:
        - inline_comment: cleaned comment (may be empty string)
        """

        split_str = re.split(self.PATTERN_LINE_COMMENT, line)
        inline_comment = [split_str[-1]] if len(split_str) == 2 else ''

        return inline_comment


    def clean_comment_lines(self, lines_raw: list[str], includes_inline: bool = False) -> list[str]:
        """Clean list of strings of up to (and including, if includesInline=True)
        an object or parameter definition
        
        Arguments:
        - lines_raw: list of lines that may contain comments
        - includes_inline: whether the last entry in the list should be
            parsed as an inline comment
        Returns:
        - lines_new: cleaned list of comments (may be empty list)
        """
        
        if includes_inline:
            # Treat last line as inline comment and previous lines as block comment
            block_comment = self.clean_comment_block(lines_raw[:-1])
            inline_comment = self.clean_inline_comment(lines_raw[-1])
            lines_new = block_comment + [inline_comment]
        else:
            # Treat lines as block comment
            lines_new = self.clean_comment_block(lines_raw)
        
        lines_new = [s.strip() for s in lines_new if s.strip()]
        
        return lines_new


    def parse_object_comments(self, lines_raw: list[str]) -> dict:
        """Clean and parse list of lines prior to an object definition.
        May contain a block comment or individual line comments. If it contains 
        unrelated lines of code, these will be filtered out.

        Tries to find NatSpec tags, if any; either way, keeps full comment and sets
        a one-line description.
            
        Arguments:
        - lines_raw: list of lines that may contain relevant comments
        Returns:
        - comment_dict: contains the following:
            - tag:value items for any NatSpec tags used. For 'param', value is
                dict of param:description items
            - 'full_comment' and 'description' keys for full (cleaned) comment
                string and one-line description
        """

        comment_data = {}    
        
        # Clean lines and skip the rest if no comment found
        lines = self.clean_comment_lines(lines_raw, includes_inline=False)  

        if len(lines) == 0:
            return comment_data
        
        # Add tag values, if NatSpec is used
        split_lines = re.split(r'\n@([a-z]+)', '\n' + '\n'.join(lines))[1:] 
        if len(split_lines) > 0:
            natspec_values = zip(split_lines[::2], split_lines[1::2])
            for (tag, value) in natspec_values:
                prev_value = comment_data.get(tag, '')
                if not prev_value:
                    comment_data[tag] = value.replace('\n', ' ').strip()
                else:
                    comment_data[tag] = prev_value + '\n' + value.replace('\n', ' ').strip()
        
        # Split parameters (if any) into a dictionary
        params = comment_data.get('param', '')
        if params:
            paramLines = [s.split(' ', 1) for s in params.split('\n')]
            comment_data['param'] = {p[0]: p[1] for p in paramLines}
        
        comment_data['full_comment'] = '\n'.join(lines)  

        # Control flow for choosing main description
        tags = comment_data.keys()
        if 'title' in tags:
            description = comment_data['title']
        elif 'notice' in tags:
            description = comment_data['notice']
        elif 'dev' in tags:
            description = comment_data['dev']
        elif 'return' in tags:
            description = comment_data['return']
        else:
            description = comment_data['full_comment'].split('.')[0]
        
        comment_data['description'] = description
        
        return comment_data


    def parse_parameter_comments(self, lines_raw: list[str]) -> dict:
        """Clean and parse list of lines up to and including a parameter definition.
        May contain a block comment or individual line comments. If it contains 
        unrelated lines of code, these will be filtered out.
            
        Arguments:
        - lines_raw (list(str)): list of lines that may contain relevant comments
        Returns:
        - comment_data (dict): contains the following:
            - 'full_comment' and 'description' keys for full (cleaned) comment
                string and one-line description
        """

        comment_data = {}

        # Clean lines and skip the rest if no comment found
        lines = self.clean_comment_lines(lines_raw, includes_inline=True)
        
        if len(lines) == 0:
            return comment_data    
    
        # Strip any tags from the description
        lines_noTags = [re.split(r'@[a-z]+', s)[-1].strip() for s in lines]
        
        # Identify inline comment and set description from that or block comment
        has_inline_comment = (lines[-1] in lines_raw[-1])
        if has_inline_comment and len(lines) == 1:
            # Only inline comment, no prior comments
            inline = lines[0]
            description = inline
        elif has_inline_comment:
            # Inline and prior line comments
            description = ' '.join(lines_noTags[:-1])
            inline = lines_noTags[-1]
        else:
            # Only prior line comments, no inline comment
            description = ' '.join(lines_noTags)
            inline = ''

        comment_data['full_comment'] = '\n'.join(lines)       
        comment_data['description'] = description
        comment_data['inline_comment'] = inline
        
        return comment_data


    def add_docstring_comments(self, lines: list[str], df_objects: DataFrame, df_parameters: DataFrame) -> DataFrame:
        """Parse comments and add them to the relevant rows in the DataFramess"""

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
            comment_end = row['line_numbers'][0] - 1
            if prevObjectLoc[1] <= comment_end:
                comment_start = prevObjectLoc[1]
            else:
                comment_start = prevObjectLoc[0]
            commentLines = lines[comment_start:comment_end]
            comment_data = self.parse_object_comments(commentLines)

            # Add object descriptions to objects
            for key, value in comment_data.items():
                if key in df_o.columns:
                    if key == 'param':
                        value = list(value.keys())
                    df_o.iat[i, df_o.columns.get_loc(key)] = value               

            # Add parameter descriptions to parameters
            for param_name, param_description in comment_data.get('param', {}).items():
                index = df_p.loc[(df_p['object_name']==row['object_name']) &
                                (df_p['parameter_name']==param_name)].index[0]
                df_p.iat[index, df_p.columns.get_loc('description')] = param_description

            prevObjectLoc = row['line_numbers']

        return df_o, df_p


    def add_inline_comments(self, lines: list[str], df_parameters: DataFrame) -> DataFrame:
        """Parse comments and add them to the relevant rows in the parameter DataFrame"""

        df_p = df_parameters.copy(deep=True)
        df_p['full_comment'] = ''

        comment_start = 0
        for i, row in df_p.iterrows():   
            # Grab and parse comment lines
            comment_end = int(row['line_number'])
            commentLines = lines[min(comment_start, comment_end - 2):comment_end]
            comment_data = self.parse_parameter_comments(commentLines)
            
            # Add to dict (but don't overwrite previously found value)
            for key, value in comment_data.items():
                if key in df_p.columns:
                    currentValue = df_p.iat[i, df_p.columns.get_loc(key)]
                    if not currentValue:
                        df_p.iat[i, df_p.columns.get_loc(key)] = value

            comment_start = comment_end

        return df_p


    def remove_duplicate_comments_in_parameters(self, df_o: DataFrame, df_parameters: DataFrame) -> DataFrame:
        """Remove description and/or full comment for a parameter if it is the same
        as its parent object's description
        """
        
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
