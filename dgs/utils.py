import ast
import pandas as pd
from pandas.core.series import Series
from sklearn.preprocessing import MultiLabelBinarizer

import logging


def ast_eval(s, alt_fcn=None):
    """Evaluate strings as their properly-formated python AST equivalent,
    
    Wrapper around ast.literal_eval() to catch exceptions and return the 
    original value if there is an error
    
    Notes:
    -   Lists with commas but no brackets are parsed as tuples
    -   Space-delimited lists with brackets are not parsed correctly
    """

    try:
        result = ast.literal_eval(s)
    except:
        if alt_fcn:
            try:
                result = alt_fcn()
            except:
                result = s
        else:
            result = s

    return result


def load_result_from_file(path: str, csv_kwargs: dict = None, list_cols: list[str] = None) -> pd.DataFrame:
    """Load contract, object, or parameter data from CSV file"""

    if csv_kwargs is None:
        csv_kwargs = {}
    if list_cols is None:
        list_cols = ['line_numbers', 'inheritance', 'modifiers', 'values', 'parameters']

    df = pd.read_csv(path, **csv_kwargs) # TODO: figure out whether to include index col

    # Convert columns to list where necessary
    for col in list(set(df.columns).intersection(list_cols)):
        df[col] = df[col].apply(lambda s: ast_eval(s))
        df[col] = df[col].apply(lambda d: d if isinstance(d, list) else [])

    return df


def count_unique_values(col: Series) -> Series:
    """Return counts of each unique value in a column containing lists"""
    
    try:
        # One-hot encode column of lists
        mlb = MultiLabelBinarizer(sparse_output=True)
        df_onehot = pd.DataFrame.sparse.from_spmatrix(
            mlb.fit_transform(col),
            index=col.index,
            columns=mlb.classes_)

        # Get count for each unique item
        counts = df_onehot.sum()
        counts.name = 'count'

    except TypeError:
        logging.exception('Make sure there are no null values in the column (use empty list instead)')
        raise

    return counts


def print_groupby(gb):
    """Print pandas groupby object"""

    for key, item in gb:
        print(key)
        print(gb.get_group(key), "\n")