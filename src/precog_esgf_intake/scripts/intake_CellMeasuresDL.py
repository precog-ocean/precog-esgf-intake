"""
Sweep across the ESGF metagrid for desired ocean cell variables from
shortlisted models in the Catalogue Dataframes

"""

from multiprocessing.pool import ThreadPool
import numpy as np
import intake_esgf
import tqdm
from precog_esgf_intake.scripts.intake_UtilFuncs import *
from precog_esgf_intake.scripts.intake_esgf_mods.catalog import ESGFCatalog
pd.set_option('display.width', 2000)  # pretty printing to console
pd.set_option('display.max_columns', None)  # pretty printing to console
import datetime
from precog_esgf_intake.scripts.intake_OceanVarsDL import download_files, calculate_hash, download_non_parallel_files
from pathlib import Path
import sys
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

def import_ocean_var_dataframes():
    user_path = input(
        "Indicate either:\n"
        "1. the folder where dataframes 'DF_Downloadable_XXX.xlsx' are saved, or\n"
        "2. the full path to a single dataframe file 'DF_Downloadable_XXX.xlsx':\n"
    )
    user_path = Path(user_path.strip(" ")).expanduser()

    if user_path.exists() is False:
        raise FileNotFoundError(f"Path does not exist: {user_path}")

    # case 1: user provided a single dataframe file
    if user_path.is_file():
        if user_path.suffix != ".xlsx":
            raise ValueError(
                f"Expected an .xlsx file, got: {user_path}"
            )

        print(f"Importing single dataframe file: {user_path}")
        DF_master = pd.read_excel(user_path, engine='openpyxl')
        return DF_master

    # case 2: user provided a directory containing multiple dataframe files
    if user_path.is_dir():
        DF_master = pd.DataFrame()
        matched_files = []

        for file in os.listdir(user_path):
            if (
                'DF_Downloadable' in file
                and file.endswith(".xlsx")
                and not ('areacello' in file or 'volcello' in file)
            ):
                df_filename = os.path.join(user_path, file)
                DF_dummy = pd.read_excel(df_filename, engine='openpyxl')
                DF_master = pd.concat([DF_master, DF_dummy], ignore_index=True)
                matched_files.append(file)

        if len(matched_files) == 0:
            raise FileNotFoundError(
                f"No matching 'DF_Downloadable_*.xlsx' files found in directory: {user_path}"
            )

        print(f"Imported {len(matched_files)} dataframe file(s):")
        for file in matched_files:
            print(f" - {file}")

        return DF_master

    raise ValueError(f"Path is neither a file nor a directory: {user_path}")

def varcell_prepare_df(logger_name, variable_id):

    # Complete - TODO import all DF filtered searches and then concat source_ids to have a single list of target models.
    logger1 = logging.getLogger(logger_name)  # Reconstruct
    logger1.info(f"Importing Dataframes from filtered searches for ocean variables...")
    DF_master = import_ocean_var_dataframes() # call to function to import Dataframes for ocean variables.

    # Complete TODO find corresponding models based on filtered search
    var_id = DF_master['variable_id'].unique()
    logger1.info(f"Dataframe(s) for variable(s) {var_id} imported.")

    models_target = DF_master['source_id'].unique().tolist()

    logger1.info(f"Catalogue search started...")
    # scrape to see which ones to include
    cat = ESGFCatalog().search(
        project='CMIP6',
        # activity_drs=['CMIP', 'ScenarioMIP'],
        # experiment_id=['piControl', 'historical'],
        source_id = models_target,
        variable_id = variable_id,
    )

    print(cat)
    len(cat.df['source_id'].unique())  # n models with cell var
    logger1.info(f'There are {len(cat.df['source_id'].unique())} models with var {var} available.')
    models_cellmeasure = cat.df['source_id'].unique().sort()
    logger1.info(models_cellmeasure)

    # dictionary structure containing all the urls, SHA256 hashes to enable serialised download
    info = cat.infos_to_dict(quiet=False)
    DataFrameSearch = pd.DataFrame.from_dict(info['https'])

    logger1.info(f'Building dataframe with catalogue search results for var {var}...')
    DF_cellmeasure = append_cols(PandasDataFrame=DataFrameSearch)

    # Check if all models shortlisted have been picked up in the search for cell measure (either areacello or volcello, depends on what the user entered):
    test_list = [model in DF_cellmeasure['source_id'].unique().tolist() for model in models_target]

    logger1.info(f'Checking all shortlisted models to find corresponding {var} file:')

    for test, model in zip(test_list, models_target):
        logger1.info(f"Found {var} for model {model}? {test}")

    logger1.info('Summary of test was:')

    if all(test_list):
        logger1.info(f"Found cell variable {var} for all models shortlisted for var {var_id}:")

    else:
        res = [i for i, val in enumerate(test_list) if not val]
        for idx in res:
            logger1.info(f"Cell variable {var} for model {models_target[idx]} not found.")

    # Now traverse to fnd best match for cell measure
    # First find target unique keys
    indices_to_grab = []
    keys = DF_master['key'].unique().tolist()  # these need to be stripped of var_ids and frequency and replaced with right string
    keys_twin = DF_master['key'].unique().tolist()
    for key in keys:
        parts = key.split('.')
        parts_twin = key.split('.')

        for idx in range(0, len(parts)):
            if parts[idx] in var_id:  # if the part of the key has any of the vars (theta, o2, so, epc100) then replace by 'areacello' or another cell measure
                parts[idx] = var
                parts_twin[idx] = var

            #if model output is only available as time varying ('0mon') then also look for the fixed counterpart gridcell measures 'Ofx' in case no '0mon' is found.
            if parts[idx] == 'Omon':
                parts_twin[idx] = 'Ofx'
            #print(key)

        key = '.'.join(parts)
        key_twin = '.'.join(parts_twin)

        idx = DF_cellmeasure.index[DF_cellmeasure['key'] == key]
        if idx.size != 0:
            idx = int(idx[0])
            indices_to_grab.append(idx)

        # if model output is only available as time varying ('0mon') then also look for the fixed counterpart gridcell measures 'Ofx' in case no '0mon' is found.
        idx2 = DF_cellmeasure.index[DF_cellmeasure['key'] == key_twin]
        if idx2.size != 0:
            idx2 = int(idx2[0])
            indices_to_grab.append(idx2)


    indices_to_grab = np.unique(indices_to_grab)

    DF_cellmeasure_filtered = DF_cellmeasure[DF_cellmeasure.index.isin(indices_to_grab)]

    ####### now relaxing criteria and creating regex to get cell measure from another variant label (e.g., *r2i1p1f2) and concat to DF_cellmeasure filtered
    keys = DF_master['key']  # these need to be stripped of var_ids and frequency and replaced with right string
    keys_target_wild = []
    for key in keys:
        parts = key.split('.')
        parts[
            0:3] = '*'  # with each replacement, the list shrinks so indexes change. That's why we need to keep clumping and breaking
        key = '.'.join(parts)
        parts = key.split('.')
        parts[2:5] = '*'
        key = '.'.join(parts)
        parts = key.split('.')
        for idx in range(0, len(parts)):
            if parts[
                idx] in var_id:  # if the part of the key has any of the vars (theta, o2, so, epc100) then replace by 'areacello' or another cell measure
                parts[idx] = var

        key = '.'.join(parts)  # this key should then get a wildcard '*' added
        keys_target_wild.append(key)

    DF_master['key_wildcards'] = keys_target_wild

    # now onto the regex step
    keys_cm = DF_cellmeasure['key']
    keys_cm_wild = []
    for key in keys_cm:
        parts = key.split('.')
        parts[
            0:3] = '*'  # with each replacement, the list shrinks so indexes change. That's why we need to keep clumping and breaking
        key = '.'.join(parts)
        parts = key.split('.')
        parts[2:5] = '*'
        key = '.'.join(parts)  # this key should then get a wildcard '*' added
        keys_cm_wild.append(key)

    DF_cellmeasure['key_wildcards'] = keys_cm_wild

    model_found = []
    DF_cellmeasure_relaxed_regex = pd.DataFrame(columns=DF_cellmeasure.columns)

    DF_cellmeasure_relaxed_regex[
        "file_start"] = None  # this is added to suppress verbose warnings for columns where date-time types in 'file_start' and 'file_end' cols show inconsistencies in data types
    DF_cellmeasure_relaxed_regex["file_end"] = None

    ##################
    # now looping through all regex matches for each model (sometimes we get over 100s of hits per single model for areacello or volcello)
    ##################
    for row in tqdm(range(0, len(DF_master)), total=len(DF_master)):
        # print(row)
        DF_single = DF_master.iloc[row]
        target_key = DF_single['key_wildcards']
        model = DF_single['source_id']

        if model not in model_found:  # will skip loop if next row in master dataframe represents a model that's been searched already

            matches = DF_cellmeasure.index[DF_cellmeasure[
                                               'key_wildcards'] == target_key]  # these are indices where a match in the 'wild_cards' from both dataframes were found
            if matches.size != 0:
                logger1.info(f"\nFound possible matches for {target_key} in cell measure dataframe for model {model}.")
                logger1.info(f"Indices for files in cell measure dataframe are {matches}")
                model_found.append(model)

                ##now check if all shortlisted file sizes are the same
                DF_cellmeasure_shortlisted = DF_cellmeasure[DF_cellmeasure.index.isin(matches)]
                DF_cellmeasure_selected = DF_cellmeasure_shortlisted.iloc[
                    [0]]  # copy first line to initiate dataframe that will be concatenated

                # account for cases where file size values are different and shrink dataframe to shortlist one instance of each option and download both to check later
                vals = DF_cellmeasure_shortlisted['size'].unique().tolist()
                vals.sort()

                if len(vals) != 1:
                    logger1.info(f"Model {model} has duplicate {var} files with {len(vals)} different sizes.Registering for later inspection.\n")
                else:
                    logger1.info(f"Model {model} has no duplicate {var} files.\n")

                processed = []
                for val in vals:
                    if val not in processed:
                        for idx in range(0, len(DF_cellmeasure_shortlisted)):
                            if DF_cellmeasure_shortlisted.iloc[idx]['size'] == val:
                                DF_cellmeasure_selected = pd.concat([DF_cellmeasure_selected, DF_cellmeasure_shortlisted.iloc[[idx]]])
                                # print(f"Processed {val}")
                                break # break from checking size loop as only a single copy is needed to be appended
                        processed.append(val)

                # getting all but first entry, which was copied to initialised the dataframe
                DF_cellmeasure_selected = DF_cellmeasure_selected.iloc[1:]

                ##now appending results back to filtered dataframe
                DF_cellmeasure_relaxed_regex = pd.concat([DF_cellmeasure_relaxed_regex, DF_cellmeasure_selected])

                # TODO complete subset save a subset dataframe per model for the cell measure inside the model folder to check in the future
                short_path = os.path.join(download_path, 'CMIP6', model, var)
                if not os.path.exists(short_path):
                    os.makedirs(short_path)
                DF_cellmeasure_selected.to_excel(os.path.join( short_path, model + "_" + var + ".xlsx"))

    ##################
    # now check if urls are downloadable
    logger1.info('Checking server responses from file urls...')
    df_downloadable = link_traverser(DF_cellmeasure_filtered, logger_name=logger_name)
    ##################

    logger1.info('Appending simpler local paths for saving individual files...')

    # build a patch with a column containing a simpler local path so that files are saved closer to model root directory rather than down a tree of directories:
    paths = []
    for row in range(0, len(DF_cellmeasure_filtered)):
        model = DF_cellmeasure_filtered.iloc[row]['source_id']
        file_name = DF_cellmeasure_filtered.iloc[row]['path']
        file_name = file_name.name
        path = os.path.join(download_path, 'CMIP6', model, var, file_name)  # this is the directory structure where cell measures are saved
        paths.append(path)

    df_downloadable['local_path'] = paths
    save_searched_tests(df_downloadable_tested=df_downloadable, downloadpath=download_path)
    logger1.info(f"Checks complete. Dataframe exported to {download_path}")
    logger1.info('########=END=#######\n')

    return None


if __name__ == "__main__":

    ####### PRECOG HEADER #######
    print_precog_header()

    today = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")  # get today's flag and hour stamp for saving unique files later on

    # Complete TODO Prompt user for input to indicate the download path or by dragging folder onto terminal
    ### Defining paths and loading dataframes
    download_path = input("Define the download path. Either type path or drag desired download parent folder (e.g. PRECOG-DATA) onto this terminal window:")
    download_path = Path(download_path.strip(" ")) #strip added as dragging onto terminal adds a trailing 'space'

    if os.path.isdir(download_path) == False:
        os.mkdir(download_path)

    logfilename = os.path.join(os.path.normpath(download_path), f"ESGF_SearchLog")

    ####### PATCHING CACHED BEHAVIOUR TO ALLOW SAVING DATE IN CUSTOM DIR #######
    original_cache_path = '~/.esgf/'  # place it back if user wishes to retrieve some of the functionality using cached dir
    intake_esgf.conf.set(all_indices=True, local_cache=download_path, confirm_download=True)
    # print(intake_esgf.conf)

    #user prompt for cell measures
    print("Please enter the variable name for ocean grid measures. For example, type 'areacello' or 'volcello':")
    var = input()
    var = eval(var).strip(" ")  # delete any trailing spaces
    while var not in ['areacello', 'volcello']:
        print("Please enter the variable name for ocean grid measures in the correct format. For example, type 'areacello' or 'volcello'")
        var = input()
        var = eval(var).strip(" ")  # delete any trailing spaces

    print(f"User entered cell variable name: {var}")
    #printing to logger
    logger1 = instantiate_logging_file(logfilename + f"_{str(var)}" + f"_{today}.txt", logger_name=str(var)) # start the logger
    logger1.info("Please enter the variable name for ocean grid measures. E.g. type 'areacello' or 'volcello':")
    logger1.info(f"User entered cell variable name: {var}")
    filename = os.path.join(os.path.normpath(download_path), f"DF_Downloadable_{var}" + ".xlsx")

    ####### CATALOGUE SEARCH #######
    # Complete - TODO check to see if downloadable DF has already been exported.
    #  If yes, then ask whether user wants a new catalogue search or skip to triggering downloads
    logger1.info(f"Checking if a post-processed Dataframe file for {var} already exists on {download_path}...")
    if not os.path.isfile(filename):
        logger1.info(f'File {filename} not found. Performing a catalogue search...')
        ####### TRIGGER MAIN FUNCTION #######
        varcell_prepare_df(logger_name=str(var), variable_id=var)
    else:
        logger1.info(f'File {filename} found.')
        u_response = input(f"Type 'new' if you want a new catalogue search for {var}.\nAlternatively, type 'skip' to trigger downloads using existing Dataframe file {filename}:\n")
        if u_response.lower().strip() == "'new'":
            logger1.info('Starting new catalogue search...')
            varcell_prepare_df(logger_name=str(var), variable_id=var)

    ####### SENSE CHECK: IMPORTING UPDATED or EXISTING DATAFRAMES FOR CELL MEASURES #######
    print(f"Now either drag onto terminal or type path to Dataframe with the Filtered ESGF search results for var {var}:")
    df_filename = input()
    df_filename = Path(df_filename.strip(" ")).name  # strip needed as dragging onto terminal adds a trailing 'space'
    print('Checking if Dataframe is readable')
    print(os.path.isfile(os.path.join(download_path, df_filename)))
    print(f'Importing Dataframe {df_filename}')
    df_downloadable = pd.read_excel(os.path.join(download_path, df_filename))

    # TODO logging file: append exception catching from within download_files function
    today = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dl_name = df_filename.split('DF_Downloadable_')[1].split('.xlsx')[0]
    log_dl_path = os.path.join(download_path, f"ESGF_DownloadLog_{log_dl_name}_{today}.txt")
    logger_dld = instantiate_logging_file(log_dl_path, logger_name=str(log_dl_name)) # start the logger

    ####### NOW ONTO DOWNLOADING FILES #######
    # prompt for user input
    print(f'There are {len(df_downloadable)} files totalling {(sum(df_downloadable['size']) / 1e9):.2f} Gb for variable(s) {df_downloadable['variable_id'].unique().tolist()}')
    user_input = input("Do you want to trigger downloads? (yes/no): ")
    user_input = user_input.strip(" ")
    if user_input.lower() in ["yes", "y"]:
        print("Continuing...\n")

        df_downloadable_fast = df_downloadable[df_downloadable['DownloadableParallel']==True] # filter DF by DownloadableParallel column flags
        # parallelizing download
        iterable_dwnld = []
        for i in range(0, len(df_downloadable)):
            # building_iterable
            df_single = df_downloadable.iloc[[i]]
            iterable_dwnld.append(
                (df_single, download_path, logger_dld))  # this is the iterable being passed to the download function with 2 args

        with  ThreadPool(processes=2) as pool:
            pool.starmap(download_files, iterable_dwnld, chunksize=4)  # starmap unpacks the iterable args to function

        for idx, row in df_downloadable_fast.iterrows():
            # get filename
            filename = os.path.basename(df_downloadable_fast.iloc[idx]['local_path'])
            output_path = os.path.join(download_path, df_downloadable_fast.iloc[idx]['local_path'])
            if os.path.exists(output_path) and calculate_hash(output_path) == df_downloadable_fast.iloc[idx]['checksum']:
                logger_dld.info(f"Skipping {filename} (already exists and is intact)")
                df_downloadable_fast.at[idx, 'DownloadedToDisk'] = True

        #start the serialised download using wget for any leftovers and include those files flagged as having more strict mirrors
        df_serialised = download_non_parallel_files(df=df_downloadable, download_path=download_path, logger=logger_dld)

        #Concatenate df_fast_dl and dl_serialised and overwrite DF
        DF_updated = pd.concat([df_downloadable_fast, df_serialised])
        DF_updated.to_excel(os.path.join(download_path, df_filename), index=False)

        logger_dld.info('Parallel and serialised Download sweep complete \n')

        print('Download sweep complete \n')

    else:
        print("Exiting...\n")

    ####### MOTIVATIONAL QUOTE #######
    print('\n')
    print_precog_footer()
    logger1.info(f'Grid cell measures should have been saved at {os.path.join(download_path, 'CMIP6')}')
    logger1.info('You got the data. Now go be amazing!')























































