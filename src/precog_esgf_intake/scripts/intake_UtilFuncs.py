import ast
import os
import random
import textwrap
import threading
import subprocess
import pandas as pd
import time
import logging
import requests
from tqdm.auto import tqdm
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from ascii_magic import AsciiArt
import datetime
import sys
import shlex
import tomllib
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def print_precog_header():
    print("\n" * 2)
    my_art = AsciiArt.from_image('./misc_images/precog_logo_full.png')  # path to logo image
    my_art.to_terminal(width_ratio=3)
    print("\n" * 2)
    return None

def print_coffee():
    print("\n" * 2)
    my_art = AsciiArt.from_image('./misc_images/CoffeeMug.png')  # path to logo image
    my_art.to_terminal(columns=80, width_ratio=3)
    print("\n" * 2)
    return None

def print_precog_footer():
    end_art = AsciiArt.from_image('./misc_images/squid2.png')
    end_art.to_terminal(columns=80, width_ratio=2.5)
    print("\n" * 2)
    return None


def load_search_criteria_toml(search_criteria_path):
    """
    Load and validate a TOML file containing ESGF search criteria.

    Expected structure
    ------------------
    [search]
    project = ["CMIP6"]
    activity_drs = ["CMIP", "ScenarioMIP"]
    experiment_id = ["piControl", "historical"]
    frequency = ["mon"]
    variable_id = ["expc", "o2"]
    grid_label = ["gn", "gr"]

    Parameters
    ----------
    search_criteria_path : str or pathlib.Path
        Path to the TOML file to read.

    Returns
    -------
    dict
        Dictionary with validated search criteria and validation options.

    Raises
    ------
    FileNotFoundError
        If the TOML file does not exist.
    KeyError
        If required sections or keys are missing.
    TypeError
        If fields are of the wrong type.
    ValueError
        If logically invalid combinations are found.
    """
    search_criteria_path = Path(search_criteria_path).expanduser()

    if search_criteria_path.is_file() is False:
        raise FileNotFoundError(f"Could not find TOML search criteria file: {search_criteria_path}")

    with open(search_criteria_path, "rb") as handle:
        config = tomllib.load(handle)

    if "search" not in config:
        raise KeyError("Missing required [search] section in TOML file.")

    search_defaults = {
        "project": ["CMIP6"],
        "activity_drs": ["CMIP", "ScenarioMIP"],
        "experiment_id": ["piControl", "historical"],
        "frequency": ["mon"],
        "variable_id": [],
        "grid_label": ["gn", "gr"],
    }

    search_cfg = config.get("search", {})

    search_final = {**search_defaults, **search_cfg}

    required_list_fields = [
        "project",
        "activity_drs",
        "experiment_id",
        "frequency",
        "variable_id",
        "grid_label",
    ]

    for field in required_list_fields:
        if isinstance(search_final[field], str):
            search_final[field] = [search_final[field]]

        if isinstance(search_final[field], list) is False:
            raise TypeError(
                f"Field [search].{field} must be a list of strings or a single string."
            )

        if all(isinstance(item, str) for item in search_final[field]) is False:
            raise TypeError(
                f"Field [search].{field} must contain only strings."
            )

    if len(search_final["variable_id"]) == 0:
        print("Field [search].variable_id is empty in TOML file. Script will prompt user interactively.")

    final_config = {
        "search": search_final,
    }

    print("The search will consider the following criteria from TOML:")
    print("###########")
    for key, value in final_config["search"].items():
        print(f"{key}: {value}")
    print("###########")

    return final_config


def append_cols(PandasDataFrame):
    col_names = ['source_id', 'experiment_id', 'variant_label', 'frequency', 'variable_id', 'grid_label']
    positional_order = [3, 4, 5, 6, 7, 8]

    for col, idx in zip(col_names, positional_order):
        print(f"Extracting info from dataset_id the following facet: '{col}' which appears as argument number: {idx}")
        PandasDataFrame[[col]] = PandasDataFrame["dataset_id"].apply(lambda x: pd.Series(str(x).split(".")[idx]))

    return PandasDataFrame  # this is the dataframe with appended columns that make it easier to sort and cross-check across models and variables


def patch_date(DataFrameSubset):
    # get file name to strip dates from

    DataFrameSubset_patched = DataFrameSubset.copy(deep=True)

    for idx in range(0, len(DataFrameSubset_patched['path'])):
        # intentionally ensure this is a Path data type otherwise it clunks sometimes and tries to convert to string unintentionally.
        fname = DataFrameSubset_patched['path'][idx]
        fname = Path(fname)

        start_dt = fname.name.split('_')[-1].split('.nc')[0].split('-')[0]
        start_dt_1 = datetime.date(year=int(start_dt[:4]), month=int(start_dt[4:]), day=1)
        start_dt_1 = pd.Timestamp(start_dt_1)  # ('YYYY-MM-DD HH:MM:SS')

        end_dt = fname.name.split('_')[-1].split('.nc')[0].split('-')[-1]
        end_dt_1 = datetime.date(year=int(end_dt[:4]), month=int(end_dt[4:]), day=1)
        end_dt_1 = pd.Timestamp(end_dt_1)  # ('YYYY-MM-DD HH:MM:SS')

        if DataFrameSubset_patched.loc[idx, 'file_start'] == None:
            DataFrameSubset_patched.loc[idx, 'file_start'] = start_dt_1

        if DataFrameSubset_patched.loc[idx, 'file_end'] == None:
            DataFrameSubset_patched.loc[idx, 'file_end'] = end_dt_1

    return DataFrameSubset_patched


def check_var_in(ConcatDF, varlist):
    catch_state = []
    for var in varlist:
        df1_subset_var = ConcatDF.loc[ConcatDF['variable_id'] == var]  # subsetting for a single variable

        if len(df1_subset_var) == 0:  # in case any catalogue entries do not have results for the variable, then move on to the next model
            # print(f"Model {model} returned {len(df1_subset_var)} entries for variable {var}")
            catch_state.append(False)
        else:
            catch_state.append(True)
    return catch_state


def check_continuity(DataFrameSubset, run, logger):
    DataFrameSubset = DataFrameSubset.sort_values(by=['file_start']).reset_index(drop=True)
    var = DataFrameSubset['variable_id'].unique().tolist()
    model = DataFrameSubset['source_id'].unique().tolist()

    # some fetched dates are returning 'None' for file_start and file_end columns.
    # So it needs to be built and patched manually. Example is model ['SAM0-UNICON']
    if None in DataFrameSubset['file_start'].unique() or None in DataFrameSubset['file_end'].unique():
        print('Date patching needed. Function to correct date formats triggered.')
        DataFrameSubset = patch_date(DataFrameSubset)

    date_strs_start = DataFrameSubset['file_start'].reset_index(drop=True)
    date_strs_end = DataFrameSubset['file_end'].reset_index(drop=True)

    # Complete TODO fix data column so when exporting to spreadsheet all dates for file_start and file_end have the same date format
    # example of date being saved wrong

    # example of date output
    # #o2_Omon_CanESM5_piControl_r1i1p1f1_gn_520101-521012.nc'
    # # 'file_start': Timestamp('5201-01-01 00:00:00'), 'file_end': Timestamp('5210-12-01 00:00:00)'
    # check if both columns have a datatype as 'Timestamp' so that operations can be done on dates, if not convert to Timestamp
    if type(date_strs_start.values[0]) == str:
        date_strs_start = [pd.Timestamp(value) for value in date_strs_start.values]

    if type(date_strs_end.values[0]) == str:
        date_strs_end = [pd.Timestamp(value) for value in date_strs_end.values]

    # gap_in_file = date_strs_end[0].date().year - date_strs_start[0].date().year #the year time step within each nc file
    # gap_across_file = date_strs_start[1].date().year-date_strs_start[0].date().year #the year time step between consecutive nc files

    gaps_within = [j.date().year - i.date().year for i, j in
                   zip(date_strs_start, date_strs_end)]  # #the year gap within each nc file

    if len(DataFrameSubset) != 1:  # if there's more than one nc file
        single_file = False
        gaps_across = [j.date().year - i.date().year for i, j in
                       zip(date_strs_start[:-1],
                           date_strs_start[1:])]  # the year time step between consecutive nc files
        # padding with an extra dummy line for loop to work
        date_strs_start_pad = pd.concat([date_strs_start, pd.Series(date_strs_start.iloc[-1])]).reset_index(drop=True)
        date_strs_end_pad = pd.concat([date_strs_end, pd.Series(date_strs_end.iloc[-1])]).reset_index(drop=True)

        gaps_within.append(gaps_within[-1])

        gaps_across.append(gaps_across[-1])  # repeat line as across always has size n-1
        gaps_across.append(gaps_across[-1])

        range_padded = list(range(0, len(date_strs_start) + 1))

        traverser = list(zip(date_strs_start_pad, date_strs_end_pad, gaps_within, gaps_across, range_padded))

        consecutive_test = []
        counter = 0
        logger.info(f'Checking if {run} run for variable {var} in {model} is consecutive')
        # print(f'Checking if {run} run for variable {var} in {model} is consecutive')
        for i in range(0, len(traverser) - 1):
            a, b, gap_lat_i, gap_vert_i, indx_i = traverser[i]
            c, d, gap_lat_ii, gap_vert_ii, indx_ii = traverser[i + 1]
            if (a.date().year + gap_lat_i == b.date().year
                    and b.date().year + 1 == c.date().year
                    and c.date().year + gap_lat_ii == d.date().year):
                logger.info(f'{traverser[i][0]} and {traverser[i + 1][0]}')
                counter += 1
                consecutive_test.append(True)

            else:
                consecutive_test.append(False)

            if i + 1 == len(traverser) - 1:  # prints last line once reaches the end
                logger.info(f'{traverser[i][0]} and {traverser[i + 1][1]}')
                # print(f'{traverser[i][0]} and {traverser[i + 1][1]}')

    else:  # in case there's only one nc file
        logger.info(f'Single model output file for run {run}, consider checking. Otherwise it is considered continuous')
        # print(f'Single model output file for run {run}, consider checking. Otherwise, it is considered continuous')
        single_file = True
        counter = 1
        consecutive_test = [True, True]

    return counter, single_file, consecutive_test[:-1]  # removes the last boolean of consecutive_test because this involves the padded test


def catalog_traverser(logger, CatalogDF, varlist):
    if type(varlist) == type(
            'str'):  # if evaluates to a single variable passed as a string (i.e., not a list of strings)
        varlist = [varlist]  # then force it to be a list

    models = CatalogDF['source_id'].unique().tolist()
    models_to_discard = []  # incomplete models (either lack pi or historical)
    model_DF_test_grids_concatenated = pd.DataFrame(
        columns=['grid_label', 'var_test', 'variable_ids', 'has_all_variables', 'run', 'model'])
    df_downloadable = pd.DataFrame(
        columns=['key', 'dataset_id', 'checksum_type', 'checksum', 'size', 'HTTPServer', 'OPENDAP', 'Globus', 'path',
                 'file_start', 'file_end', 'source_id', 'experiment_id', 'variant_label', 'frequency', 'variable_id',
                 'grid_label'])

    for model in models:
        # check if complete/contiguous piControl followed by historical run in both thetao, so and o2 searches
        df1_subset = CatalogDF.loc[CatalogDF['source_id'] == model]

        # TODO make sure each dataframe is continuous with respect to picontrol and historical runs across all variables

        variables_in = check_var_in(df1_subset, varlist)  # checks if any of the variables returns an empty dataframe, if they all return entries then proceed

        if not all(variables_in):
            logger.info(
                f'The model: {model} does not have all variable(s) of interest: test for {varlist} returned {variables_in} \n')
            models_to_discard.append(model)

        elif all(variables_in):  # for the models which have all variables of interest

            # TODO add grid avail check across all variables
            test_grids_pi = check_grid_avail(df1_subset, varlist, grid_labels=['gn', 'gr'], run='piControl',
                                             logger=logger)
            test_grids_historical = check_grid_avail(df1_subset, varlist, grid_labels=['gn', 'gr'], run='historical',
                                                     logger=logger)

            # todo merge both dictionaries and turn into dataframe to export for further inspection and logging
            model_DF_test_grids = pd.concat(
                [pd.DataFrame.from_dict(test_grids_pi), pd.DataFrame.from_dict(test_grids_historical)])
            model_DF_test_grids_concatenated = pd.concat([model_DF_test_grids_concatenated,
                                                          model_DF_test_grids])  # append to master dataframe which is exported at the end with grid and var comparissons

            # check if at least 1 piControl and 1 historical run have all vars in either grid
            # complete todo test two conditions
            lack_pI = model_DF_test_grids.loc[
                (model_DF_test_grids["run"] == 'piControl') & (model_DF_test_grids["has_all_variables"] == True)].empty
            lack_historical = model_DF_test_grids.loc[
                (model_DF_test_grids["run"] == 'historical') & (model_DF_test_grids["has_all_variables"] == True)].empty

            if not lack_pI and not lack_historical:
                logger.info(
                    f'The model: {model} has variables: test for {varlist} returned {variables_in} for both piControl and historical runs.OBS: grid may vary')

                # clean df1_subset so that only gridded files that passed the test are kept in the dataframe
                grid_to_keep = model_DF_test_grids.loc[model_DF_test_grids["has_all_variables"] == True]
                grids_kept = list(set(list(grid_to_keep['grid_label'])))

                filter = df1_subset['grid_label'].isin(grids_kept)
                df1_subset_filtered = df1_subset[filter]

                for var in varlist:

                    df1_subset_var = df1_subset_filtered.loc[df1_subset_filtered['variable_id'] == var]
                    # now checking continuity between piControl and Historical for each variable
                    logger.info(f'Now checking continuity between piControl and Historical for variable {var}')

                    df1_pi = df1_subset_var.loc[
                        df1_subset_var['experiment_id'] == 'piControl']  # subsetting into temporary dataframes
                    df1_historical = df1_subset_var.loc[df1_subset_var['experiment_id'] == 'historical']

                    # checking if both piControl and Historical runs exist for all variables # this is redundant #check if ok to remove for simplicity
                    if len(df1_pi) == 0 or len(df1_historical) == 0:
                        if len(df1_pi) == 0:
                            logger.info(f'No piControl run for model {model} for variable {var}')
                            # TODO remove model from list
                            models_to_discard.append(model)
                            continue

                        if len(df1_historical) == 0:
                            logger.info(f'No Historical run for model {model} for variable {var}')
                            # TODO remove model from list
                            models_to_discard.append(model)
                            continue

                    else:
                        logger.info(f'Found both piControl and Historical runs for model {model} for variable {var}')
                        # check if only one variant and that the variant matches across piControl and Historical

                        # if more than one variant passed, then grab simplest and check if also present in historical. Drop other variants
                        variant_in_common = set(df1_pi['variant_label'].unique()).intersection(
                            df1_historical['variant_label'].unique())
                        # now dropping whatever variant is not captured by intersection
                        df1_pi = df1_pi[df1_pi['variant_label'].isin(list(variant_in_common))]
                        df1_historical = df1_historical[df1_historical['variant_label'].isin(list(variant_in_common))]

                        if variant_in_common:
                            logger.info(
                                f'Variant labels {variant_in_common} from piCrontrol and Historical in model {model} are matching')

                            # check piControl and Historical continuity in dates for each variable
                            # Complete TODO check continuity piControl pass to function
                            counter_piControl, single_file_pi, consecutive_piControl = check_continuity(df1_pi,
                                                                                                        run='piControl',
                                                                                                        logger=logger)  # check piControl continuity
                            if all(consecutive_piControl):
                                logger.info(f'piControl run for variable {var} in {model} looks consecutive')
                                logger.info(f'number of piControl files is {counter_piControl + 1} END\n')

                            # check Historical continuity
                            # complete TODO same scheme as above but for historical run
                            counter_historical, single_file_historical, consecutive_historical = check_continuity(
                                df1_historical, run='historical', logger=logger)
                            if all(consecutive_historical):
                                logger.info(f'Historical run for variable {var} in {model} looks consecutive')
                                logger.info(f'number of Historical files is {counter_historical + 1} END \n')

                            if all(consecutive_piControl) and all(consecutive_historical):
                                df_downloadable = pd.concat([df_downloadable, df1_pi, df1_historical], axis=0)

                            if not all(consecutive_piControl) or not all(consecutive_historical):
                                models_to_discard.append(
                                    model)  # shows which models have both piControl and Historical runs for the following variables: thetao, so, o2, and expc
                                logger.info(
                                    f'Either piControl or Historical runs for model {model} for variable {var} is not continuous')
                                logger.info('\n')

                        else:
                            models_to_discard.append(model)
                            raise ValueError(
                                f'Mismatch between available variant lables \n {df1_pi["variant_label"].unique()} is different from {df1_historical["variant_label"].unique()}')


            else:
                logger.info('\n')
                logger.info(
                    f'No complete set of variables for model {model} for variable {varlist} in either grid. Test returned:')
                string_pretty = ''.join(['#'] * 140)
                logger.info(string_pretty)
                [logger.info(_) for _ in model_DF_test_grids.to_string(index=False).split('\n')]
                logger.info(string_pretty)
                logger.info('\n')
                models_to_discard.append(model)

    return models_to_discard, model_DF_test_grids_concatenated, df_downloadable


def catalog_traverser_ensemble(logger, CatalogDF, varlist, pi_anchor_keys):
    """
    Traverse a catalogue dataframe in ensemble mode.

    Core ensemble logic
    -------------------
    1. Select one piControl anchor per (source_id, grid_label), precomputed in
       `pi_anchor_keys` as the lowest acceptable variant.
    2. Validate that piControl anchor across all variables in `varlist`.
    3. Retain every historical variant on the same (source_id, grid_label) that:
       - is complete across `varlist`
       - passes continuity checks for all variables

    Parameters
    ----------
    logger : logging.Logger
        Logger used for verbose screening output.
    CatalogDF : pandas.DataFrame
        Catalogue dataframe containing piControl and historical rows.
    varlist : list[str] or str
        Variables required for completeness.
    pi_anchor_keys : pandas.DataFrame
        One-row-per-anchor dataframe with columns:
        ['source_id', 'grid_label', 'variant_label'].
        This should already represent the chosen lowest piControl anchor for each
        (source_id, grid_label).

    Returns
    -------
    models_to_discard : list[str]
        Models rejected because no valid grid / anchor / historical members survived.
    model_DF_test_grids_concatenated : pandas.DataFrame
        Grid-level diagnostics dataframe from check_grid_avail().
    df_downloadable : pandas.DataFrame
        Final downloadable dataframe containing:
        - one validated piControl anchor per kept (source_id, grid_label)
        - all valid historical variants on that same (source_id, grid_label)
    """
    if isinstance(varlist, str):
        varlist = [varlist]

    required_anchor_cols = ['source_id', 'grid_label', 'variant_label']
    missing_anchor_cols = [c for c in required_anchor_cols if c not in pi_anchor_keys.columns]
    if missing_anchor_cols:
        raise KeyError(f"pi_anchor_keys missing required columns: {missing_anchor_cols}")

    models_to_discard = []
    model_DF_test_grids_concatenated = pd.DataFrame()
    df_downloadable = pd.DataFrame(columns=CatalogDF.columns)

    for model in sorted(CatalogDF['source_id'].dropna().unique().tolist()):
        logger.info(f'\n')
        logger.info(f"================ MODEL: {model} ================")

        DataFrameSubsetModel = CatalogDF.loc[CatalogDF['source_id'] == model].copy()

        if DataFrameSubsetModel.empty:
            logger.info(f"No rows found for model {model}.")
            models_to_discard.append(model)
            continue

        # -------------------------------------------------------------
        # 1. Identify grids that are valid in both piControl and historical
        # -------------------------------------------------------------
        test_grids_pi = check_grid_avail(
            DataFrameSubsetModel=DataFrameSubsetModel,
            varlist=varlist,
            grid_labels=['gn', 'gr'],
            run='piControl',
            logger=logger
        )

        test_grids_historical = check_grid_avail(
            DataFrameSubsetModel=DataFrameSubsetModel,
            varlist=varlist,
            grid_labels=['gn', 'gr'],
            run='historical',
            logger=logger
        )

        model_DF_test_grids = pd.concat(
            [
                pd.DataFrame.from_dict(test_grids_pi),
                pd.DataFrame.from_dict(test_grids_historical)
            ],
            ignore_index=True
        )

        model_DF_test_grids_concatenated = pd.concat(
            [
                model_DF_test_grids_concatenated,
                model_DF_test_grids
            ],
            ignore_index=True
        )

        valid_pi_grids = set(
            model_DF_test_grids.loc[
                (model_DF_test_grids["run"] == "piControl") &
                (model_DF_test_grids["has_all_variables"] == True),
                "grid_label"
            ].tolist()
        )

        valid_historical_grids = set(
            model_DF_test_grids.loc[
                (model_DF_test_grids["run"] == "historical") &
                (model_DF_test_grids["has_all_variables"] == True),
                "grid_label"
            ].tolist()
        )

        valid_grids = sorted(list(valid_pi_grids.intersection(valid_historical_grids)))

        if len(valid_grids) == 0:
            logger.info(
                f"Model {model} does not have a common valid grid across piControl "
                f"and historical for {varlist}. Discarding model.\n"
            )
            models_to_discard.append(model)
            continue

        df_model_keep = pd.DataFrame(columns=CatalogDF.columns)

        for grid in valid_grids:
            logger.info(f"--- Processing model {model} on grid {grid} ---")

            # -------------------------------------------------------------
            # 2. Recover the single precomputed piControl anchor for model/grid
            # -------------------------------------------------------------
            anchor_keys_this = pi_anchor_keys.loc[
                (pi_anchor_keys['source_id'] == model) &
                (pi_anchor_keys['grid_label'] == grid)
            ].copy()

            if anchor_keys_this.empty:
                logger.info(
                    f"Model {model}, grid {grid}: no piControl anchor key found."
                )
                continue

            if len(anchor_keys_this) > 1:
                logger.info(
                    f"Model {model}, grid {grid}: multiple anchor rows found; "
                    f"expected one lowest anchor only. Keeping first row."
                )
                anchor_keys_this = anchor_keys_this.iloc[[0]].copy()

            anchor_variant = anchor_keys_this['variant_label'].iloc[0]
            logger.info(
                f"Model {model}, grid {grid}: using piControl anchor variant "
                f"{anchor_variant}"
            )

            df_pi = CatalogDF.loc[
                (CatalogDF['source_id'] == model) &
                (CatalogDF['grid_label'] == grid) &
                (CatalogDF['experiment_id'] == 'piControl')
            ].copy()

            df_pi_anchor = df_pi.merge(
                anchor_keys_this,
                on=['source_id', 'grid_label', 'variant_label'],
                how='inner'
            )

            if df_pi_anchor.empty:
                logger.info(
                    f"Model {model}, grid {grid}: anchor key exists but no "
                    f"piControl rows matched it."
                )
                continue

            # -------------------------------------------------------------
            # 3. Validate piControl anchor across varlist
            # -------------------------------------------------------------
            anchor_var_test = check_var_in(df_pi_anchor, varlist)
            if not all(anchor_var_test):
                logger.info(
                    f"Model {model}, grid {grid}: piControl anchor is not complete "
                    f"across {varlist}."
                )
                continue

            pi_anchor_ok = True

            for var in varlist:
                df_pi_anchor_var = df_pi_anchor.loc[
                    df_pi_anchor['variable_id'] == var
                ].copy()

                if df_pi_anchor_var.empty:
                    pi_anchor_ok = False
                    logger.info(
                        f"Model {model}, grid {grid}: anchor missing piControl "
                        f"variable {var}."
                    )
                    break

                counter_pi, single_file_pi, consecutive_test_pi = check_continuity(
                    df_pi_anchor_var,
                    run='piControl',
                    logger=logger
                )

                if not all(consecutive_test_pi):
                    pi_anchor_ok = False
                    logger.info(
                        f"Model {model}, grid {grid}: piControl anchor continuity "
                        f"failed for variable {var}."
                    )
                    break

            if not pi_anchor_ok:
                continue

            # -------------------------------------------------------------
            # 4. Retain all valid historical variants on the same model/grid
            # -------------------------------------------------------------
            df_hist = CatalogDF.loc[
                (CatalogDF['source_id'] == model) &
                (CatalogDF['grid_label'] == grid) &
                (CatalogDF['experiment_id'] == 'historical')
            ].copy()

            if df_hist.empty:
                logger.info(f"Model {model}, grid {grid}: no historical rows found.")
                continue

            hist_counts = (
                df_hist.groupby('variant_label')['variable_id']
                .nunique()
                .reset_index(name='n_var')
            )

            hist_complete_variants = hist_counts.loc[
                hist_counts['n_var'] == len(varlist),
                'variant_label'
            ].tolist()

            if len(hist_complete_variants) == 0:
                logger.info(
                    f"Model {model}, grid {grid}: no historical variants are complete "
                    f"across {varlist}."
                )
                continue

            hist_variants_to_keep = []

            for hist_variant in sorted(hist_complete_variants):
                df_hist_variant = df_hist.loc[
                    df_hist['variant_label'] == hist_variant
                ].copy()

                hist_variant_ok = True

                for var in varlist:
                    df_hist_var = df_hist_variant.loc[
                        df_hist_variant['variable_id'] == var
                    ].copy()

                    if df_hist_var.empty:
                        hist_variant_ok = False
                        logger.info(
                            f"Model {model}, grid {grid}, historical {hist_variant}: "
                            f"missing variable {var}."
                        )
                        break

                    counter_hist, single_file_hist, consecutive_test_hist = check_continuity(
                        df_hist_var,
                        run='historical',
                        logger=logger
                    )

                    if not all(consecutive_test_hist):
                        hist_variant_ok = False
                        logger.info(
                            f"Model {model}, grid {grid}, historical {hist_variant}: "
                            f"continuity failed for variable {var}."
                        )
                        break

                if hist_variant_ok:
                    hist_variants_to_keep.append(hist_variant)

            if len(hist_variants_to_keep) == 0:
                logger.info(
                    f"Model {model}, grid {grid}: no historical variants survived "
                    f"completeness + continuity checks."
                )
                continue

            logger.info(
                f"Model {model}, grid {grid}: keeping historical variants "
                f"{hist_variants_to_keep}"
            )

            df_hist_keep = df_hist.loc[
                df_hist['variant_label'].isin(hist_variants_to_keep)
            ].copy()

            # -------------------------------------------------------------
            # 5. Append one anchor + all valid historical variants
            # -------------------------------------------------------------
            df_grid_keep = pd.concat(
                [df_pi_anchor, df_hist_keep],
                ignore_index=True
            )

            df_model_keep = pd.concat(
                [df_model_keep, df_grid_keep],
                ignore_index=True
            )

        if df_model_keep.empty:
            logger.info(
                f"Model {model} did not yield any downloadable rows in ensemble mode.\n"
            )
            models_to_discard.append(model)
            continue

        df_downloadable = pd.concat(
            [df_downloadable, df_model_keep],
            ignore_index=True
        )

    # Deduplicate using scalar identity columns only
    dedupe_cols = [
        'source_id',
        'experiment_id',
        'variant_label',
        'variable_id',
        'grid_label'
    ]

    # Prefer scalar file-level identifiers when available.
    # Do not use HTTPServer here, because it can be list-valued and therefore
    # unhashable inside drop_duplicates().
    if 'path' in df_downloadable.columns:
        dedupe_cols.append('path')
    elif 'dataset_id' in df_downloadable.columns:
        dedupe_cols.append('dataset_id')

    df_downloadable = (
        df_downloadable
        .drop_duplicates(subset=dedupe_cols)
        .reset_index(drop=True)
    )

    return models_to_discard, model_DF_test_grids_concatenated, df_downloadable


def build_picontrol_anchor_keys(PiAnchorDF, varlist, logger=None):
    """
    Build a dataframe of piControl anchor keys from a dataframe that already
    represents the piControl-only result after remove_ensembles().

    Parameters
    ----------
    PiAnchorDF : pd.DataFrame
        Dataframe built from piControl-only catalog results after
        cat.remove_ensembles().
    varlist : list[str] | str
        Variables required for completeness.
    logger : logging.Logger | None

    Returns
    -------
    pd.DataFrame
        Unique anchor keys with columns:
        ['source_id', 'grid_label', 'variant_label']
    """
    if isinstance(varlist, str):
        varlist = [varlist]

    required_cols = ['source_id', 'grid_label', 'variant_label', 'variable_id']
    missing = [c for c in required_cols if c not in PiAnchorDF.columns]
    if missing:
        raise KeyError(f'PiAnchorDF missing required columns: {missing}')

    # only keep anchor groups complete across varlist
    pi_counts = (
        PiAnchorDF.groupby(['source_id', 'grid_label', 'variant_label'])['variable_id']
        .nunique()
        .reset_index(name='n_var')
    )

    anchor_keys = pi_counts.loc[
        pi_counts['n_var'] == len(varlist),
        ['source_id', 'grid_label', 'variant_label']
    ].drop_duplicates().reset_index(drop=True)

    if logger is not None:
        logger.info(
            f'Built {len(anchor_keys)} piControl anchor key rows from '
            f'remove_ensembles()-collapsed piControl results.'
        )

    return anchor_keys


def check_grid_avail(DataFrameSubsetModel, varlist, grid_labels, run, logger):
    # tests if all variables being queried have matching grids
    # example: Even though NorESM2-LM has thetao and so for the native grid, it does not have o2, then flag it and do not intake native grid files.
    # ...NorESM2-LM has all thetao, so, and o2 in the regular grid tho, so this should be included and processed further

    model = list(DataFrameSubsetModel['source_id'].unique())[0]
    DataFrameSubsetModel_run = DataFrameSubsetModel.loc[DataFrameSubsetModel['experiment_id'] == run]
    catch_state = True

    dict = {'grid_label': [],
            'var_test': [],
            'variable_ids': [],
            'has_all_variables': [],
            'run': [],
            'model': []}

    for grid in grid_labels:
        DataFrameSubsetModel_grid = DataFrameSubsetModel_run.loc[
            DataFrameSubsetModel_run['grid_label'] == grid]  # subsetting for a grid type
        # now get list of vars available in that specific grid:
        var_test = list(DataFrameSubsetModel_grid['variable_id'].unique())
        vart_test_mod = set(var_test)
        varlist_mod = set(varlist)

        if vart_test_mod == varlist_mod:  # test if model has a grid output across all variables of interest
            logger.info(
                f'Model {model} has the output(s) for variable(s) {varlist_mod} in a {grid} grid for the {run} run')

            catch_state = True
            var_test_final = [i == j for i, j in zip(varlist_mod, vart_test_mod)]

        else:
            missing_var = varlist_mod - vart_test_mod #gets the set difference
            logger.info(
                f'Model {model} does not have output(s) for variable(s) {varlist} in a {grid} grid for the {run} run')
            logger.info(f'Test returned the following var(s) only {vart_test_mod}')
            logger.info(f'Variable {missing_var} is missing. Ignoring model output for grid {grid}.\n')

            # padding for comparison between lists
            vart_test_mod = sorted(list(vart_test_mod)) # turn it back to a list
            varlist_mod = sorted(list(varlist_mod))

            string_flag = '!' #append symbol next to var to indicate absence
            for missing in missing_var:
                idx = varlist_mod.index(missing)
                vart_test_mod.insert(idx, missing + string_flag)

            # find indices of missing items and append them to specific positions followed by "!"
            catch_state = False
            var_test_final = [i == j for i, j in zip(varlist_mod, vart_test_mod)]

        dict['var_test'].append(var_test_final)
        dict['run'].append(run)
        dict['has_all_variables'].append(catch_state)
        dict['model'].append(model)
        dict['variable_ids'].append(varlist_mod)
        dict['grid_label'].append(grid)

    return dict


def save_tested_outputs_by_mode(df_downloadable_tested, downloadpath, ensemble_mode):
    """
    Save tested downloadable-search results using a filename prefix that
    reflects the ensemble handling mode.

    Parameters
    ----------
    df_downloadable_tested : pandas.DataFrame
        DataFrame after link_traverser() checks.
    downloadpath : str or pathlib.Path
        Output directory for the spreadsheet.
    ensemble_mode : str
        Either 'single' or 'ensemble'.
    """
    prefix_map = {
        "single": "DF_Downloadable",
        "ensemble": "DF_Downloadable_Ensemble",
    }

    if ensemble_mode not in prefix_map:
        raise ValueError(f"Unsupported ensemble_mode for saving outputs: {ensemble_mode}")

    save_searched_tests(
        df_downloadable_tested=df_downloadable_tested,
        downloadpath=downloadpath,
        file_prefix=prefix_map[ensemble_mode],
    )


def instantiate_logging_file(logfilename, logger_name):
    formatter_line_style = '%(asctime)s - %(levelname)-8s - %(message)s'
    # Create a logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Create a formatter to define the log format
    formatter = logging.Formatter(formatter_line_style)

    # Create a file handler to write logs to a file
    file_handler = logging.FileHandler(logfilename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Create a stream handler to print logs to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # You can set the desired log level for console output
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def text_align(message):
    # The header length for '%(asctime)s - %(levelname)-8s - '
    # is usually 23 (time) + 3 (separator) + 8 (level) + 3 (separator) = ~37 chars
    header_width = 37

    # Wrap the message. subsequent_indent is the magic part.
    wrapped_lines = textwrap.fill(
        message,
        width=140,  # Total line width before wrapping
        subsequent_indent=' ' * header_width,
        break_long_words=True,  # Forces a break even if there's no space
    )
    return wrapped_lines


def check_url_validity(iterable):

    urls = iterable[0]
    file_ids = iterable[1]
    links_working = []
    file_downloadable = []
    # 1. STAGGERED START: Wait a random amount of time (0-3 seconds)
    # This prevents the firewall from seeing a 'cluster' of connections
    time.sleep(random.uniform(0.5, 3.0))

    # Convert headers to a string format curl understands
    user_agent_val = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    header_string = f"User-Agent: {user_agent_val}"
    # Use a thread-safe cookie file name
    cookie_fn = f"session_{threading.get_ident()}_{random.randint(1, 1000)}.txt"

    for url in urls:
        # 1. Clean Protocol: Directly hit https to skip the 302 headache
        url = url.replace("http://", "https://") if url.startswith("http://") else url
        try:
            time.sleep(random.uniform(0.8, 1.5))  # More variance helps bypass firewalls

            # We call the system's 'curl' directly
            # -I: HEAD request (metadata only)
            # -L: Follow redirects
            # -k: Insecure (ignore SSL issues)
            # -s: Silent mode
            # --max-time: Timeout in seconds
            # --location-trusted - ensure headers are passed to the redirected URL

            command = [
                'curl', '-I', '-L', '-k', '--http1.1', '--location-trusted',
                '-H', header_string,
                '-H', 'Accept: */*',
                '-H', 'Connection: close',  # Tell the server not to wait for us
                '-b', cookie_fn, '-c', cookie_fn,
                '--max-time', '20',
                '--retry', '2',  # Auto-retry on Code 52
                '--retry-delay', '3',
                url
            ]

            # Convert list to a shell-safe string
            cmd_string = " ".join(shlex.quote(arg) for arg in command)

            result = subprocess.run(
                cmd_string,
                capture_output=True,
                text=True,
                shell=True,
                env=os.environ,
            )
            output = result.stdout
            error_msg = result.stderr

            # #DEBUGGING
            # if not output:
            #     # If stdout is empty, the secret is in stderr
            #     print(f"DEBUG: URL {url} returned EMPTY stdout.")
            #     print(f"DEBUG: STDERR says: {error_msg}")
            #
            #     # Check if curl even exists/ran
            #     if result.returncode != 0:
            #         print(f"DEBUG: Curl exited with error code {result.returncode}")

            sucess_indicators = ["200 OK", "206 Partial Content", "HTTP/2 200"]
            if any(ind in output for ind in sucess_indicators):
                lower_out = output.lower()
                # Check if it's a file, but also accept 'netcdf' or 'stream'
                if any(t in lower_out for t in ["octet-stream", "netcdf", "binary"]):
                    links_working.append((True, url, file_ids, "Success"))
                    break # Found a working mirror

            else:# If we got here, it failed. Capture the output for debugging.
                links_working.append((False, url, file_ids, output))

        except Exception as e:
            links_working.append((False, url, file_ids, f"Subprocess Error: {str(e)}"))
            continue

    #Always try to clean up the cookie file
    if os.path.exists(cookie_fn):
        try: os.remove(cookie_fn)
        except: pass

    # Wrap up the results
    is_valid = any([sublist[0] for sublist in links_working])
    file_downloadable.append(is_valid)

    return (links_working, file_downloadable)


def link_traverser(DownloadableDF, logger_name):
    logger = logging.getLogger(logger_name)  # Reconstruct
    # now traverse through dataframes named df_downloadable testing links for good connection - Complete - TODO change this to function

    DownloadableDF_tested = DownloadableDF.copy()  # make a copy so that original DF being passed does not change in memory. Good for debugging.
    ##############
    # First building an iterable to benefit from multiprocessing:
    iterable = []

    for idx in range(0, len(DownloadableDF_tested)):
        nested_url_list = [DownloadableDF_tested.iloc[idx]['HTTPServer']]
        flattened_list = [item for sublist in nested_url_list for item in sublist]
        file_id = DownloadableDF_tested.iloc[idx]['path']
        iterable.append((flattened_list, file_id))

    ## Complete - TODO build iterator with (file_id, [flattened list of urls]) to pass to multithreading function for the whole dataset
    with (ThreadPoolExecutor(max_workers=4) as executor):
        future = list(tqdm(executor.map(check_url_validity, iterable), total=len(iterable)))

    # unpacking results from generator 'future' into variable 'collector'
    collector = []
    for result in future:
        collector.append(result)

    ###############################################################
    # collector unwraps the url server handshake results in the form of :
    # collector[file_idx][0 - access url tests individually]
    # collector[file_idx][0][sub url result] - returns the tuple for that url test
    # collector[file_idx][0][sub url result][0] - returns True or False for individual url
    # collector[file_idx][0][sub url result][1] - returns individual url
    # collector[file_idx][0][sub url result][2] - returns filename
    # collector[file_idx][1 - boolean for the file if any of the links tested is_downloadable]
    ###############################################################

    # reset index of DataFrame
    DownloadableDF_tested = DownloadableDF_tested.reset_index(inplace=False, drop=False)

    state = []  # dummy array to store downloadable tests results - this will become a column in the dataframe

    # in the loop below item = collector[file_idx]
    for item in collector:
        if item[1][0] == False:  # this checks first value in collector[file_idx][1]
            logger.info(f'File {os.path.basename(item[0][0][2])} not downloadable')  # look above for navigation onto the nested lists
        state.append(item[1][0])
    # appending new column to dataframe

    DownloadableDF_tested['Downloadable'] = None
    # new column on DF to store Parallel DL status
    DownloadableDF_tested['DownloadableParallel'] = None

    for idx, val in enumerate(state):
        DownloadableDF_tested.loc[idx, 'Downloadable'] = val
        DownloadableDF_tested.loc[idx, 'DownloadableParallel'] = val

    #gentle scraping loop
    probe_size = 2**18 #this is 256KB
    false_count = (DownloadableDF_tested['Downloadable'] == False).sum()

    max_iterations = 10
    i=0
    while int(false_count)> 0 and i <= max_iterations:
        logger.info(f"Found {false_count} files for which the Downloadable flag returned FALSE during parallel scraping")
        DownloadableDF_tested = update_downloadable_column(DownloadableDF_tested, logger_name, probe_size) # overwrite DF with gentle scraping
        false_count = (DownloadableDF_tested['Downloadable'] == False).sum() # check again if any False instances
        i+=1

    #appending local paths
    local_paths = []  # dummy array to store local paths where results can be saved to - this will become a column in the dataframe
    path_start = 'CMIP6'
    for _ in DownloadableDF_tested['path']:
        pth = Path(path_start, *list(_.parts[3:]))  # build path only with those
        local_paths.append(pth)
    # appending new column to dataframe
    DownloadableDF_tested['local_path'] = None
    for idx, val in enumerate(local_paths):
        DownloadableDF_tested.loc[idx, 'local_path'] = val

    DownloadableDF_tested['DownloadedToDisk'] = False

    return DownloadableDF_tested


# User-Agent rotation for when we do URL probing
AGENTS = [
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def is_url_viable_fast(url_list_str, logger_name, probe_bytes=2 ** 18):  # 256KB
    logger = logging.getLogger(logger_name)
    """Returns True if ANY URL viable. FAST 256KB probe, max 3 URLs."""
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(AGENTS)})

        url_list = list(set(url_list_str))

        for url in url_list:  # First 3 URLs only
            try:
                resp = session.get(
                    url, stream=True,
                    timeout=(10, 20),
                    headers={'Accept': '*/*', 'Range': f'bytes=0-{probe_bytes - 1}'},
                    allow_redirects=True
                )

                if resp.status_code in (200, 206) and len(resp.content) > 1024:
                    logger.info(f"{url.split('/')[-1]}: VIABLE")
                    session.close()
                    return True


                time.sleep(0.5)

            except:
                continue

        session.close()
        return False

    except:
        return False

def update_downloadable_column(df, logger_name, probe_bytes=2 ** 18):

    logger = logging.getLogger(logger_name)
    """Update master DF: FALSE → TRUE where viable."""
    false_mask = df['Downloadable'] == False
    original_false = false_mask.sum()

    logger.info(f"Starting serialised scanning of {original_false} files flagged initially as Downloadable == FALSE... ")
    logger.info(f"This is done to mimic human browsing and avoid ESGF mirror IP blocks when scraping the existence of many files")
    viable_count = 0

    for idx in df[false_mask].index:
        row = df.loc[idx]
        if is_url_viable_fast(row['HTTPServer'], logger_name , probe_bytes):
            df.at[idx, 'Downloadable'] = True
            viable_count += 1

        time.sleep(random.uniform(2, 4))  # ESGF-safe
    if viable_count != original_false:
        logger.info(f"Updated {viable_count}/{original_false} rows")
        logger.info(f"Looping over the remaining files again")
    else:
        logger.info(f"Updated {original_false}/{viable_count} rows")
        logger.info('All rows updated successfully')
    return df

def save_searched_tests(df_downloadable_tested, downloadpath, file_prefix):
    df_name_dummy = df_downloadable_tested['variable_id'].unique().tolist()
    df_name = '_'.join(df_name_dummy)
    fname = os.path.join(downloadpath, file_prefix + "_" + df_name)
    with pd.ExcelWriter(fname + '.xlsx', engine='openpyxl') as writer:
        df_downloadable_tested.to_excel(writer)


def import_ocean_std_names(root_proj):
    for root, dirs, files in os.walk(root_proj):
        for name in files:
            if 'CMIP6_OceanVarNames.xlsx' in name:
                std_file_DF = pd.read_excel(os.path.join(root, name))
                std_names = std_file_DF['Variable Name'].to_list()
    return std_names