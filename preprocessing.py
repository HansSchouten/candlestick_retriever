import os
from datetime import date, datetime, timedelta

import pandas as pd

def set_dtypes(df):
    """
    set datetimeindex and convert all columns in pd.df to their proper dtype
    assumes csv is read raw without modifications; pd.read_csv(csv_filename)"""

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.set_index('open_time', drop=True)

    df = df.astype(dtype={
        'open': 'float64',
        'high': 'float64',
        'low': 'float64',
        'close': 'float64',
        'volume': 'float64',
        'close_time': 'datetime64[ms]',
        'quote_asset_volume': 'float64',
        'number_of_trades': 'int64',
        'taker_buy_base_asset_volume': 'float64',
        'taker_buy_quote_asset_volume': 'float64',
        'ignore': 'float64'
    })

    return df


def set_dtypes_compressed(df):
    """Create a `DatetimeIndex` and convert all critical columns in pd.df to a dtype with low
    memory profile. Assumes csv is read raw without modifications; `pd.read_csv(csv_filename)`."""

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.set_index('open_time', drop=True)

    df = df.astype(dtype={
        'open': 'float32',
        'high': 'float32',
        'low': 'float32',
        'close': 'float32',
        'volume': 'float32',
        'number_of_trades': 'uint16',
        'quote_asset_volume': 'float32',
        'taker_buy_base_asset_volume': 'float32',
        'taker_buy_quote_asset_volume': 'float32'
    })

    return df


def assert_integrity(df):
    """make sure no rows have empty cells or duplicate timestamps exist"""

    assert df.isna().all(axis=1).any() == False
    assert df['open_time'].duplicated().any() == False


def quick_clean(df):
    """clean a raw dataframe"""

    # drop dupes
    dupes = df['open_time'].duplicated().sum()
    if dupes > 0:
        df = df[df['open_time'].duplicated() == False]

    # sort by timestamp, oldest first
    df.sort_values(by=['open_time'], ascending=False)

    # just a doublcheck
    assert_integrity(df)

    return df


def addMissingMinutes(initialData):
    """
    Repeat entries to fill up for missing minutes.

    """
    cleanData = []
    previousRow = []
    for row in initialData:
        if len(previousRow) and row['datetime'] - previousRow['datetime'] > timedelta(minutes=1):
            current = previousRow.copy()
            while current['datetime'] + timedelta(minutes=1) < row['datetime']:
                current['datetime'] = current['datetime'] + timedelta(minutes=1)
                current['volume'] = 0
                current['quote_asset_volume'] = 0
                current['number_of_trades'] = 0
                current['taker_buy_base_asset_volume'] = 0
                current['taker_buy_quote_asset_volume'] = 0
                current['low'] = current['close']
                current['high'] = current['close']
                current['open'] = current['close']
                missingRow = current.copy()
                cleanData.append(missingRow)

        previousRow = row.copy()
        cleanData.append(row)

    return cleanData

def addMissingMinutesDf(df):
    """
    Repeat entries of the given dataframe to fill up for missing minutes.
    
    """
    historicalDataDict = addMissingMinutes(df.to_dict('records'))
    historicalData = pd.DataFrame(historicalDataDict)
    return historicalData


def write_raw_to_parquet(df, full_path):
    """takes raw df and writes a parquet to disk"""

    # some candlesticks do not span a full minute
    # these points are not reliable and thus filtered
    df = df[~(df['open_time'] - df['close_time'] != -59999)]

    # `close_time` column has become redundant now, as is the column `ignore`
    df = df.drop(['close_time', 'ignore'], axis=1)

    df = set_dtypes_compressed(df)

    # give all pairs the same nice cut-off
    #df = df[df.index < str(date.today())]

    # post processing for FDA
    df['datetime'] = df.index
    df.reset_index(drop=True, inplace=True)
    df = addMissingMinutesDf(df)
    df.reset_index(drop=True, inplace=True)

    df.to_parquet(full_path)


def groom_data(dirname='data'):
    """go through data folder and perform a quick clean on all csv files"""

    for filename in os.listdir(dirname):
        if filename.endswith('.csv'):
            full_path = f'{dirname}/{filename}'
            quick_clean(pd.read_csv(full_path)).to_csv(full_path)


def compress_data(dirname='data'):
    """go through data folder and rewrite csv files to parquets"""

    os.makedirs('compressed', exist_ok=True)
    for filename in os.listdir(dirname):
        if filename.endswith('.csv'):
            full_path = f'{dirname}/{filename}'

            df = pd.read_csv(full_path)

            new_filename = filename.replace('.csv', '.parquet')
            new_full_path = f'compressed/{new_filename}'
            write_raw_to_parquet(df, new_full_path)
