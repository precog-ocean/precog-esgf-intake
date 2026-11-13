"""
Sweep across the ESGF metagrid for desired ocean variables and test PI
and Historical run alignment and shortlists for cases where both PI and Historical have both
direct carbon export outputs (expc and epc100) or auxiliary vars (thetao, o2 and so).

"""

import intake_esgf
from precog_esgf_intake.scripts.intake_UtilFuncs import *
from precog_esgf_intake.scripts.intake_esgf_mods.catalog import ESGFCatalog
import datetime
import pandas as pd
pd.set_option('display.width', 2000)  # pretty printing to console
pd.set_option('display.max_columns', None)  # pretty printing to console
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

print_precog_header()

today = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")  # get today's flag and hour stamp for saving unique files later on

### Defining paths
download_path = input("Define the download path. Either type path or drag desired download parent folder onto this terminal window:")
download_path = Path(download_path.strip(" "))  # strip added as dragging onto terminal adds a trailing 'space'

if os.path.isdir(download_path) == False:
    os.mkdir(download_path)

filename = os.path.join(os.path.normpath(download_path),
                        f"ESGF_Search_{today}" + ".xlsx") #dataframe with master search results
logfilename = os.path.join(os.path.normpath(download_path),
                           f"ESGF_SearchLog")

# place it back onto intake_esgf.conf.set(local_cache=XXX)
# if user wishes to retrieve some of the functionality using cached dir
original_cache_path = '~/.esgf/'

#print(intake_esgf.conf)
intake_esgf.conf.set(all_indices=False,
                     local_cache=download_path,
                     confirm_download=True)
print('\n')
print("======= Printing config. set up for the upcoming ESGF search =======")
print(intake_esgf.conf)

# WHAT WE ARE INTERESTED IN
print("========== The search will consider as default: ========== ")
DefaultSearchParam = {
    "project": ['CMIP6'],
    "activity_drs": ['CMIP', 'ScenarioMIP'],
    "experiment_id": ['piControl', 'historical'],
    "frequency": ['mon'],
    "variable_id": [],
    "grid_label": ['gn', 'gr']
}
for key, value in DefaultSearchParam.items():
    print(f"{key}: {value}")
print("====================================================================\n")

# overwrite defaults from TOML file if provided
search_criteria_toml = Path(__file__).resolve().parent / "search_criteria.toml"
chosen_vars_from_toml = None

if search_criteria_toml.is_file():
    print(f"Detected TOML search criteria file at: {search_criteria_toml}")
    config_search = load_search_criteria_toml(search_criteria_toml)

    # overwrite the defaults with TOML-defined values
    DefaultSearchParam.update(config_search["search"])

# if variable list is still empty, prompt user interactively
if len(DefaultSearchParam["variable_id"]) == 0:
    var = input(
        "No variable_id values were provided in search_criteria.toml.\n"
        "Please enter a list of strings for variable_id. "
        "E.g. ['expc'] or multiple ['expc', 'o2', 'thetao', 'so', 'o2sat', 'epc100']:\n"
    )
    var = var.strip(" ")
    print(f"User entered variable_ids: {var}")
    DefaultSearchParam["variable_id"] = ast.literal_eval(var)

print("======== Running ESGF search with the following resolved criteria ======== ")
for key, value in DefaultSearchParam.items():
    print(f"{key}: {value}")
print("====================================================================\n")

variable_ids = DefaultSearchParam["variable_id"]
experiments_must_haves = DefaultSearchParam["experiment_id"]

root_proj = os.path.dirname(os.path.abspath(__name__))

variables_of_interest = import_ocean_std_names(root_proj)
DicDataframeSearches = {'variable_names': [], 'search_results':[]} #initializing empty dic to facilitate saving data
DicDataframePiAnchors = {'variable_names': [],'search_results': []}
##
search_project = DefaultSearchParam["project"]
search_activity_drs = DefaultSearchParam["activity_drs"]
search_experiment_id = DefaultSearchParam["experiment_id"]
search_frequency = DefaultSearchParam["frequency"]
search_grid_label = DefaultSearchParam["grid_label"]
##

ensemble_mode = input(
    "Choose ensemble handling mode:\n"
    "'single' = this will return members across piControl and historical runs (sharing the exact same "
    "variant label)\n"
    "'ensemble' = lowest piControl variant as an anchor + all compatible historical variants\n"
    "Type [single/ensemble]: "
).strip().lower()

if ensemble_mode not in ["single", "ensemble"]:
    raise ValueError(f"Unsupported ensemble_mode: {ensemble_mode}")

for oceanvar in variable_ids:
    if oceanvar.lower() in variables_of_interest:
        cat = ESGFCatalog().search(
            project=search_project,
            activity_drs=search_activity_drs,
            experiment_id=search_experiment_id,
            frequency=search_frequency,
            variable_id=oceanvar,
            grid_label=search_grid_label
        )

        print(cat.model_groups().to_string())
        print(cat.model_groups().to_string())

        # Complete TODO add function to esgf-intake catalog.py file, so that download is not automatic, ...
        # rather we'd like to retrieve the attributes from the search across all nodes into a DataFrame ...
        # so we can see what is available and where, and do further filtering without having to download heaps of data unnecessarily.
        info = cat.infos_to_dict(quiet=False)  # dictionary structure containing all the urls, SHA256 hashes to enable serialized download
        DataFrameSearch = pd.DataFrame.from_dict(info['https'])  # all with monthly piControl and historical

        # Complete TODO split file name so that columns also display the following facets
        # source_id or aka model used
        # variable_id
        # experiment_id
        # frequency
        # variant_label = r<k>i<l>p<m>f<n>,
        # where k = realization_index
        # l = initialization_index
        # m = physics_index
        # n = forcing_index

        DataFrameSearch_mod = append_cols(PandasDataFrame=DataFrameSearch)

        #updating dictionary
        DicDataframeSearches['search_results'].append(DataFrameSearch_mod)
        DicDataframeSearches['variable_names'].append(oceanvar)

        # Getting piControl anchor runs for use in case the 'ensemble' mode is desired later on by the user
        cat_pi_anchor = cat.remove_ensembles()  # # filters out to keep only a single member from the ensemble (i.e.,the one with the lowest variant label (see below)
        info_pi_anchor = cat_pi_anchor.infos_to_dict(quiet=True)
        DataFrameSearch_pi_anchor = pd.DataFrame.from_dict(info_pi_anchor['https'])
        DataFrameSearch_pi_anchor_mod = append_cols(PandasDataFrame=DataFrameSearch_pi_anchor)
        DataFrameSearch_pi_anchor_mod = DataFrameSearch_pi_anchor_mod.loc[DataFrameSearch_pi_anchor_mod['experiment_id'] == 'piControl'].copy()
        DicDataframePiAnchors['search_results'].append(DataFrameSearch_pi_anchor_mod)
        DicDataframePiAnchors['variable_names'].append(oceanvar)

    else:
        raise KeyError(f'Variable {oceanvar} not found in default variables of interest {variables_of_interest}')

#Saving search results to single spreadsheet with individual dataframes where each tab is an ocean variable dataframe
with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    for idx, oceanvarname in enumerate(DicDataframeSearches['variable_names']):
        result = DicDataframeSearches['search_results'][idx]
        result.to_excel(writer, sheet_name=oceanvarname)

print("===============================================================================")
print(f"Catalogue Scraping complete and raw search results saved as a Dataframe on ...")
print(f"{filename}")
print("===============================================================================\n")

#########################
print('Now checking if we have complete piControl and Historical runs and consistent availability of grids...')
combine=input("Would you like perform a 'union' validation to check for PI and Historical runs for > 1 ocean variable?\n"
              "This is equivalent to searching for CMIP6 models that have (var1 & var2 & varN) for both PI and Historical runs. Type [y/n]:")

#Initializing dataframe objects
DFCombined = pd.DataFrame(columns=DicDataframeSearches['search_results'][0].columns)
DFCombinedPiAnchors = pd.DataFrame(columns=DicDataframePiAnchors['search_results'][0].columns)

# =========== ================= ======== #
# =========== MAIN LOOP LOGIC   ======== #
# =========== ================= ======== #

if combine.lower().strip(" ") in ['y', 'yes']:
    input_chosen = input(f"Enter which variables from the search {DicDataframeSearches['variable_names']} to combine in the form ['var1', 'var2', 'varN']:")
    input_chosen = eval(input_chosen)

    chosen_vars = input_chosen ## bundle chosen vars
    loglabelstr = ""
    for var in chosen_vars:
        loglabelstr = loglabelstr + var + "_"
    #loglabelstr = loglabelstr

    # and concatenate dataframes from dic of chosen vars
    for idx, oceanvarname in enumerate(DicDataframeSearches['variable_names']):
        if oceanvarname in chosen_vars:
            result = DicDataframeSearches['search_results'][idx]
            # print(result)
            DFCombined = pd.concat([DFCombined, result], axis=0)

   ## then pass to catalogue traverser
    logger = instantiate_logging_file(logfilename + '_' + loglabelstr + f"_{today}.txt" , logger_name=loglabelstr)

    # =========== ENSEMBLE MODE   ======== #
    if ensemble_mode == "ensemble":

        for idx, oceanvarname in enumerate(DicDataframePiAnchors['variable_names']):
            if oceanvarname in chosen_vars:
                result_pi = DicDataframePiAnchors['search_results'][idx]
                DFCombinedPiAnchors = pd.concat([DFCombinedPiAnchors, result_pi], axis=0)

        pi_anchor_keys = build_picontrol_anchor_keys(
            PiAnchorDF=DFCombinedPiAnchors,
            varlist=chosen_vars,
            logger=logger)

        logger.info("Running ensemble mode: lowest piControl anchor + all compatible historical members")
        models_to_discard, model_DF_test_grids_concatenated, df_downloadable = catalog_traverser_ensemble(logger, DFCombined, chosen_vars, pi_anchor_keys)

    # =========== SINGLE MEMBER MODE   ======== #
    else:
        logger.info("Running single-member mode")
        models_to_discard, model_DF_test_grids_concatenated, df_downloadable = catalog_traverser(logger, DFCombined, chosen_vars)

    models_to_keep = df_downloadable['source_id'].unique().tolist()
    logger.info(f"Models with complete PI and Historical runs for {chosen_vars} in at least one consistent grid ('gn' or 'gr'):")
    for model in sorted(models_to_keep):
        logger.info(model)
    logger.info('########=END OF CATALOGUE SEARCH =#######')

    # now we have a list of models to keep and also have a reduced dataframe containing all pre-downloadable files for the concatenated dataframe ('df_downloadable').
    # But still need to check if the files can actually be retrieved from endpoints
    # Saving Dataframe searches after performing url checks that tell us if the files can actually be retrieved from endpoints


    logger.info(f'Traversing urls to test server responses for combined vars {chosen_vars}')
    print_coffee()
    logger.info(f'This might take a few minutes... Coffee time?')
    df_downloadable_tested = link_traverser(df_downloadable, logger_name=loglabelstr)
    save_tested_outputs_by_mode(
        df_downloadable_tested=df_downloadable_tested,
        downloadpath=download_path,
        ensemble_mode=ensemble_mode
    )
    logger.info(f'Traversing complete for vars {chosen_vars}\n')

else:
    #then just pass single var to catalogue traverser function
    for idx, oceanvarname in enumerate(DicDataframeSearches['variable_names']):
        chosen_vars = oceanvarname
        loglabelstr = ""
        loglabelstr = oceanvarname

        ## then pass to catalogue traverser
        logger = instantiate_logging_file(logfilename + '_' + loglabelstr + f"_{today}.txt", logger_name=loglabelstr)
        logger.info(f"User chose not to combine. Checking individual variables for PI and Historical run consistency and availability of grids...")
        logger.info(f"###### Testing {oceanvarname} next ######")

        # =========== ENSEMBLE MODE   ======== #
        if ensemble_mode == "ensemble":

            df_pi_anchor_single = DicDataframePiAnchors['search_results'][idx]

            pi_anchor_keys = build_picontrol_anchor_keys(
                PiAnchorDF=df_pi_anchor_single,
                varlist=chosen_vars,
                logger=logger)

            logger.info("Running ensemble mode: lowest piControl anchor + all compatible historical members")
            models_to_discard, model_DF_test_grids_concatenated, df_downloadable = catalog_traverser_ensemble(logger,
                                                                                                     DicDataframeSearches['search_results'][idx],
                                                                                                     chosen_vars,
                                                                                                     pi_anchor_keys)
        # =========== SINGLE MEMBER MODE   ======== #
        else:
            logger.info("Running single-member mode")
            models_to_discard, model_DF_test_grids_concatenated, df_downloadable = catalog_traverser(logger,
                                                                                                     DicDataframeSearches['search_results'][idx],
                                                                                                     chosen_vars)

        models_to_keep = df_downloadable['source_id'].unique().tolist()
        logger.info(
            f"Models with complete piControl and Historical runs for {chosen_vars} in at least one consistent grid ('gn' or 'gr'):")
        for model in sorted(models_to_keep):
            logger.info(model)
        logger.info(f'########=END OF CATALOGUE SEARCH FOR VAR {chosen_vars}#######')

        # now we have a list of models to keep and also have a reduced dataframe containing all pre-downloadable files ('df_downloadable').
        # But still need to check if the files can actually be retrieved from endpoints
        # Saving Dataframe searches after performing url checks that tell us if the files can actually be retrieved from endpoints
        logger.info(f'Traversing urls to test server responses for combined vars {chosen_vars}')
        print_coffee()
        logger.info(f'This might take a few minutes... Coffee time?')
        df_downloadable_tested = link_traverser(df_downloadable, logger_name=loglabelstr)
        save_tested_outputs_by_mode(
            df_downloadable_tested=df_downloadable_tested,
            downloadpath=download_path,
            ensemble_mode=ensemble_mode
        )
        #save_searched_tests(df_downloadable_tested=df_downloadable_tested, downloadpath=download_path)
        logger.info(f'Traversing complete for var {chosen_vars}\n')

# #### SANITY CHECK #####
# First just checking if filtered full-search result and downloadable are same size when excluding odd-cases for when grid availability is missing:
# dummyDF1 = DataFrameSearch_T_S_o2[DataFrameSearch_T_S_o2['source_id'].isin(models_to_keep_T_S_o2)]
# dummyDF1 = dummyDF1.drop(['HTTPServer', 'OPENDAP', 'Globus'], axis=1)
# dummyDF2 = df_downloadable_T_S_o2.drop(['HTTPServer', 'OPENDAP', 'Globus'], axis=1)
# compareDF = dummyDF1.merge(dummyDF2, how='outer',
#                            indicator=True)  # sanity check (show that odd ones are 'left only' entries) - these are the cases where a variable for one of the grid_labels is missing

############
# Motivational quote
print_precog_footer()
print("\n")
logger.info(f'Data sweep complete.\nDataframes should have been saved at {download_path}')
logger.info(f'Now giddy up and run "~/intake_OceanVarsDL.py" to download the data.')

########### NEXT STEPS ####################
# compelte TODO add logger to print outputs
# complete TODO check if selected ESMs have working downloadable links across all files (row wise check of all indices so that request is different from 404! and requests file header actually points to a file with size > 0)
# complete TODO - New program: download each file in parallel and run check sum after completion to check for file corruption
# TODO - New program : find models after screening for pi and Historical which have forward branching simulations available in for example 'ScenarioMIP' activities
###############################
