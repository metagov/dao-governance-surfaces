import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MultiLabelBinarizer
import textwrap


SAVEDIR = 'tmp'
DEFAULT_COLOR = '#66C2A5'
DEFAULT_SIZE = (5, 5)

kwargs_svg = {'format': 'svg', 'bbox_inches': 'tight', 'transparent': True}
kwargs_png = {'format': 'png', 'bbox_inches': 'tight', 'dpi': 600, 'transparent': True}

sns.set(rc={"figure.figsize":DEFAULT_SIZE})
sns.set(font_scale=1.25)


def save_figure(plt, name, tag=None, fmt='all'):
    if tag is None:
        tag = ''
    else:
        tag = tag + ' - '
    fname = f"{SAVEDIR}/{tag}{name}"
    if fmt in ('png', 'all'):
        plt.savefig(f"{fname}.png", **kwargs_png)
    if fmt in ('svg', 'all'):
        plt.savefig(f"{fname}.svg", **kwargs_svg)



def plot_coded_column(df_all, col, saveFig=False, figParams=None, label='', orient='h', size=None, plotType='bar', scaleToMax=True):
    """Plot frequency of unique list items for coded columns
    Handle columns with list values differently from columns with single values"""
    
    df = df_all.copy(deep=True)
    isListCol = any([isinstance(d, list) for d in df[col]])
    
    if isListCol:
        # Make sure all values in column are lists
        df[col] = df[col].apply(lambda d: d if isinstance(d, list) else [])

        # One-hot encode column of lists
        mlb = MultiLabelBinarizer(sparse_output=True)
        df_onehot = pd.DataFrame.sparse.from_spmatrix(
            mlb.fit_transform(df[col]),
            index=df.index,
            columns=mlb.classes_)

        # Get count for each unique item
        df_sum = pd.DataFrame(df_onehot.sum()).sort_values(0, axis=0, ascending=False).transpose()
    else:
        df_sum = pd.DataFrame(df[col].value_counts()).transpose()
    
    # Resize plot if needed
    if size is not None:
        sns.set(rc={"figure.figsize": size})
        sns.set(font_scale=1.25)
    
    plt.figure()
    
    if plotType == 'bar':
        # Plot bar chart of unique list items
        ax = sns.barplot(data=df_sum, orient=orient, color=DEFAULT_COLOR)

        # Formatting
        if orient == 'h':
            plt.ylabel(label)
            labels = ["\n".join(textwrap.wrap(c, width=30)) for c in df_sum.columns]
            ax.set(yticklabels=labels)
            plt.xlabel('Count')
            if not isListCol and scaleToMax:
                plt.xlim((0, df_sum.sum().sum() + 1))
        else:
            plt.ylabel('Count')
            plt.xlabel("\n".join(textwrap.wrap(label, 50)))
            labels = ["\n".join(textwrap.wrap(c, width=25)) for c in df_sum.columns]
            ax.set(xticklabels=labels)
            if not isListCol and scaleToMax:
                plt.ylim((0, df_sum.sum().sum() + 1))
    
    elif plotType == 'pie':
        # Plot pie chart of unique list items
        fig = plt.pie(df_sum.squeeze(), labels=df_sum.columns, 
                      colors=sns.color_palette("Set2"), wedgeprops=dict(width=0.5))
        plt.title(label)
    
    if saveFig:
        assert figParams is not None, "Provide figParams if saveFig is True"
        save_figure(plt, **figParams)
    
    if size is not None:
        sns.set(rc={"figure.figsize": DEFAULT_SIZE})
        sns.set(font_scale=1.25)