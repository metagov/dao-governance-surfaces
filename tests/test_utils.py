import pytest
import pandas as pd

from dgs.utils import ast_eval, count_unique_values


@pytest.fixture(params=[
    [[1,2,3], [2], [4], [], [5,1]],
    [[], ['test', 'test'], ['toast'], ['twist'], ['test', 'twist']]
])
def generate_test_data_count_unique_values(request):
    """Create a DataFrame with a list-of-lists column and
    return the appropriate input and expected index for
    count_unique_values
    """

    list_of_lists = request.param
    input_df = pd.DataFrame.from_dict({'col': list_of_lists})['col']
    output_list = list(set(pd.core.common.flatten(list_of_lists)))

    return input_df, output_list


def test_count_unique_values(generate_test_data_count_unique_values):
    """Check whether the index contains the expected unique values"""

    input, expected = generate_test_data_count_unique_values
    df_unique = count_unique_values(input)
    assert sorted(list(df_unique.index)) == sorted(expected)


@pytest.mark.parametrize("input,expected", (
    ("[[1,2,3], [], [2]]", [[1,2,3], [], [2]],),
    ("['these', 'are', 'strings']", ['these', 'are', 'strings']),
    ("{'a': 1, 'b': 2, 'c': [3]}", {'a': 1, 'b': 2, 'c': [3]}),
    ("[1, None, 3]", [1, None, 3]),
    ("[]", []),
    ("None", None),
    ("['malformed' 'list']", ['malformedlist']), # A limitation, not a feature
    ("'malformed', 'list'", ('malformed', 'list')), # A limitation, not a feature
    ('this is a string', 'this is a string',),
))
def test_ast_eval(input, expected):
    assert ast_eval(input) == expected
