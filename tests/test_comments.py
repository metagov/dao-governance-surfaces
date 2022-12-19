import pytest
import os

from dgs.comments import CommentParser

@pytest.mark.parametrize("input,expected", [
    (
        [
            "    /**",
            "     * @notice Internal method to delegate execution to another contract",
            "     * @dev It returns to the external caller whatever the implementation returns or forwards reverts",
            "     * @param callee The contract to delegatecall",
            "     * @param data The raw data to delegatecall",
            "     */"
        ],
        {
            'notice': "Internal method to delegate execution to another contract",
            'dev': "It returns to the external caller whatever the implementation returns or forwards reverts",
            'param': {
                'callee': "The contract to delegatecall",
                'data': "The raw data to delegatecall"
            },
            'description': "Internal method to delegate execution to another contract",
        }
    ),
])
def test_parse_object_comments(input,expected):
    cp = CommentParser()
    comment_dict = cp.parse_object_comments(input)

    print(comment_dict)

    assert all([k in comment_dict.keys() for k in expected.keys()])
    assert all([v == comment_dict[k] for k, v in expected.items()])


@pytest.mark.parametrize("input,expected", [
    (
        [
            "",
            "    /// @notice The number of votes in support of a proposal required in order for a quorum to be reached and for a vote to succeed",
            "    uint public constant quorumVotes = 400000e18; // 400,000 = 4% of Comp",
        ],
        {
            'description': "The number of votes in support of a proposal required in order for a quorum to be reached and for a vote to succeed",
            'inline_comment': "400,000 = 4% of Comp"
        }
    ),
    (
        ["	        address implementation_,"],
        {}
    ),
])
def test_parse_parameter_comments(input,expected):
    cp = CommentParser()
    comment_dict =  cp.parse_parameter_comments(input)

    print(comment_dict)

    assert all([k in comment_dict.keys() for k in expected.keys()])
    assert all([v == comment_dict[k] for k, v in expected.items()])