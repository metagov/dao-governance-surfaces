import os
import ast
import numpy as np
import pandas as pd
from typing import Any, Iterable, Callable
from pandas.core.series import Series
from pandas.core.groupby import GroupBy
from sklearn.preprocessing import MultiLabelBinarizer

import logging


def ast_eval(s: Any, alt_fcn: Callable = None) -> Iterable:
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
                result = alt_fcn(s)
            except:
                result = s
        else:
            result = s

    return result


def load_result_from_file(path: str, csv_kwargs: dict = None, list_cols: list[str] = None) -> pd.DataFrame:
    """Load contract, object, or parameter data from CSV file"""

    if csv_kwargs is None:
        csv_kwargs = {'index_col': 0}
    if list_cols is None:
        list_cols = ['line_numbers', 'inheritance', 'modifiers', 'values', 
            'parameters', 'coding_keyword_search', 'coding_topic_search']

    df = pd.read_csv(path, **csv_kwargs) # TODO: figure out whether to include index col

    # Convert columns to list where necessary
    for col in list(set(df.columns).intersection(list_cols)):
        df[col] = df[col].apply(lambda s: ast_eval(s))
        df[col] = df[col].apply(lambda d: d if isinstance(d, list) else [])

    return df


def load_results_from_files(dir: str = 'tmp'):
    """Load all object and parameter data from CSV files in the directory"""

    # Collect DataFrames for each individual object and parameter CSV file
    all_objects = []
    all_params = []
    for filename in os.listdir(dir):
        f = os.path.join(dir, filename)
        if os.path.isfile(f):
            _df = load_result_from_file(f)
            if filename.startswith('contract_objects'):
                all_objects.append(_df)
            elif filename.startswith('contract_parameters'):
                all_params.append(_df)

    # Join into a single DF for each of objects and parameters
    df_objects = pd.concat(all_objects).set_index('id')
    df_params = pd.concat(all_params).set_index('id')

    # Load child parameter names into df_objects for ease of analysis
    df_objects['parameters_names'] = df_objects['parameters'].apply(
        lambda values: [df_params.at[v, 'parameter_name'] for v in values] if isinstance(values, list) else np.nan
    )

    # One-hot encode keywords for each
    mlb = MultiLabelBinarizer(sparse_output=True)
    df_objects_kws = pd.DataFrame.sparse.from_spmatrix(
        mlb.fit_transform(df_objects['coding_keyword_search']),
        index=df_objects.index,
        columns=mlb.classes_)
    df_objects = df_objects.join(df_objects_kws)

    return (df_objects, df_params)


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


def print_groupby(gb: GroupBy):
    """Pretty print pandas groupby object"""

    for key, item in gb:
        print(key)
        print(gb.get_group(key), "\n")