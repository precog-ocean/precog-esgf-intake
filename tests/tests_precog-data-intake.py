import ast
import hashlib
import io
import sys
import os
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__name__)))
from src.precog_esgf_intake.scripts.intake_UtilFuncs import print_precog_header, print_precog_footer
#sys.path.append('../') #This shorthand makes one module visible to the other, When modules are in parallel locations
from precog_esgf_intake.scripts.intake_esgf_mods.catalog import ESGFCatalog


def test_print_decorators():
    assert print_precog_footer() == None
    assert print_precog_header() == None

def test_search_to_dict(var='o2'):
    variable_ids = [var]
    for oceanvar in variable_ids:
        cat = ESGFCatalog().search(project='CMIP6',
                                   activity_drs=['CMIP'],
                                   experiment_id=['piControl', 'historical'],
                                   frequency='mon',
                                   variable_id=oceanvar,
                                   grid_label=['gn', 'gr'])

        cat = cat.remove_ensembles()  # filters out to keep only a single member from the ensemble (i.e., the one with the lowest variant label (see below)
        # Complete TODO add function to esgf-intake catalog.py file, so that download is not automatic, ...
        # rather we'd like to retrieve the attributes from the search across all nodes into a DataFrame ...
        # so we can see what is available and where, and do further filtering without having to download heaps of data unnecessarily.
        info = cat.infos_to_dict(
            quiet=False)  # dictionary structure containing all the urls, SHA256 hashes to enable serialised download
        DataFrameSearch = pd.DataFrame.from_dict(
            info['https'])  # all with monthly piControl and historical salinity and potential temperature

    assert bool(info) == True
    assert len(DataFrameSearch) != 0
    assert append_cols(DataFrameSearch)['variable_id'].unique() == [var]

def test_append_cols(var='thetao'):
    variable_ids = [var]
    for oceanvar in variable_ids:
        cat = ESGFCatalog().search(project='CMIP6',
                                   activity_drs=['CMIP'],
                                   experiment_id=['piControl', 'historical'],
                                   frequency='mon',
                                   variable_id=oceanvar,
                                   grid_label=['gn', 'gr'])

        cat = cat.remove_ensembles()  # filters out to keep only a single member from the ensemble (i.e., the one with the lowest variant label (see below)
        # Complete TODO add function to esgf-intake catalog.py file, so that download is not automatic, ...
        # rather we'd like to retrieve the attributes from the search across all nodes into a DataFrame ...
        # so we can see what is available and where, and do further filtering without having to download heaps of data unnecessarily.
        info = cat.infos_to_dict(
            quiet=False)  # dictionary structure containing all the urls, SHA256 hashes to enable serialised download
        DataFrameSearch = pd.DataFrame.from_dict(
            info['https'])  # all with monthly piControl and historical salinity and potential temperature

        DF = append_cols(DataFrameSearch)

    assert bool(info) == True
    assert len(DataFrameSearch) != 0
    assert append_cols(DataFrameSearch)['variable_id'].unique() == [var]
    assert set(['source_id', 'experiment_id', 'variant_label', 'frequency', 'variable_id', 'grid_label']).issubset(DF.columns)

def test_patch_date():

    df = pd.DataFrame(
        {
            "path": [Path('CMIP6/CMIP/HAMMOZ-Consortium/MPI-ESM-1-2-HAM/piControl/r1i1p1f1/Omon/expc/gn/v20200120/expc_Omon_MPI-ESM-1-2-HAM_piControl_r1i1p1f1_gn_185001-186912.nc'),
                     Path('CMIP6/CMIP/HAMMOZ-Consortium/MPI-ESM-1-2-HAM/piControl/r1i1p1f1/Omon/expc/gn/v20200120/expc_Omon_MPI-ESM-1-2-HAM_piControl_r1i1p1f1_gn_187001-188912.nc')],
            "file_start": [None, None],
            "file_end": [None, None],
        }
    )

    patched = patch_date(df)

    assert patched.loc[0, "file_start"] == pd.Timestamp(datetime.date(1850, 1, 1))
    assert patched.loc[0, "file_end"] == pd.Timestamp(datetime.date(1869, 12, 1))
    assert patched.loc[1, "file_start"] == pd.Timestamp(datetime.date(1870, 1, 1))
    assert patched.loc[1, "file_end"] == pd.Timestamp(datetime.date(1889, 12, 1))

def test_check_var_in():

    vars = ['epc100', 'o2']

    ConcatDF = pd.DataFrame()
    for oceanvar in vars:
        cat = ESGFCatalog().search(project='CMIP6',
                                   activity_drs=['CMIP'],
                                   experiment_id=['piControl', 'historical'],
                                   frequency='mon',
                                   variable_id=oceanvar,
                                   grid_label=['gn', 'gr'])

        cat = cat.remove_ensembles()  # filters out to keep only a single member from the ensemble (i.e., the one with the lowest variant label (see below)
        # Complete TODO add function to esgf-intake catalog.py file, so that download is not automatic, ...
        # rather we'd like to retrieve the attributes from the search across all nodes into a DataFrame ...
        # so we can see what is available and where, and do further filtering without having to download heaps of data unnecessarily.
        info = cat.infos_to_dict(
            quiet=False)  # dictionary structure containing all the urls, SHA256 hashes to enable serialised download
        DataFrameSearch = pd.DataFrame.from_dict(
            info['https'])  # all with monthly piControl and historical salinity and potential temperature

        DF = append_cols(DataFrameSearch)
        ConcatDF = pd.concat([ConcatDF, DF])

    vars.append('thetao')
    catch_state = []
    for var in vars : # expected behavious is catch= (True for 'epc100'), (True for 'o2') and (False for 'thetao')
        df1_subset_var = ConcatDF.loc[ConcatDF['variable_id'] == var]  # subsetting for a single variable
        if len(df1_subset_var) == 0:  # in case any catalogue entries do not have results for the variable, then move on to the next model
            # print(f"Model {model} returned {len(df1_subset_var)} entries for variable {var}")
            catch_state.append(False)
        else:
            catch_state.append(True)

    assert catch_state == [True, True, False]

def test_check_continuity():

    test_DF = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    test_DF.loc[:, 'file_start'] = None #changed on purpose to trigger patch date

    models = test_DF['source_id'].unique().tolist()
    vars = test_DF['variable_id'].unique().tolist()
    test_DF = test_DF[test_DF['variable_id'] =='o2']# single var DF
    run = 'piControl'
    o2_start = "5201-01-01"

    for model in [models[0]]:
        DataFrameSubset = test_DF[test_DF['source_id'] == model]
        DataFrameSubset = DataFrameSubset.loc[DataFrameSubset['experiment_id'] == run].reset_index(drop=True)

        if None in DataFrameSubset['file_start'].unique() or None in DataFrameSubset['file_end'].unique():
            print('Date patching needed. Function to correct date formats triggered.')
            DataFrameSubset = patch_date(DataFrameSubset)

        date_strs_start = DataFrameSubset['file_start'].reset_index(drop=True)
        date_strs_end = DataFrameSubset['file_end'].reset_index(drop=True)

        date_strs_start.values[0] = o2_start

        # check if both columns have a datatype as 'Timestamp' so that operations can be done on dates, if not convert to Timestamp
        if type(date_strs_start.values[0]) == str:
            print("converting string to timestamp")
            date_strs_start.values[0] = pd.Timestamp(date_strs_end.values[0])
            assert(DataFrameSubset.loc[0,'file_start'] == pd.Timestamp(o2_start)) # check if correctly patched

        gaps_within = [j.date().year - i.date().year for i, j in
                       zip(date_strs_start, date_strs_end)]  # #the year gap within each nc file

        if len(DataFrameSubset) != 1:  # if there's more than one nc file
            single_file = False
            gaps_across = [j.date().year - i.date().year for i, j in
                           zip(date_strs_start[:-1],
                               date_strs_start[1:])]  # the year time step between consecutive nc files

            # padding with an extra dummy line for loop to work
            date_strs_start_pad = pd.concat([date_strs_start, pd.Series(date_strs_start.iloc[-1])]).reset_index(
                drop=True)
            date_strs_end_pad = pd.concat([date_strs_end, pd.Series(date_strs_end.iloc[-1])]).reset_index(drop=True)

            gaps_within.append(gaps_within[-1])
            gaps_across.append(gaps_across[-1])  # repeat line as across always has size n-1
            gaps_across.append(gaps_across[-1])

            range_padded = list(range(0, len(date_strs_start) + 1))

            traverser = list(zip(date_strs_start_pad, date_strs_end_pad, gaps_within, gaps_across, range_padded))

            consecutive_test = []
            counter = 0

            for i in range(0, len(traverser) - 1):
                a, b, gap_lat_i, gap_vert_i, indx_i = traverser[i]
                c, d, gap_lat_ii, gap_vert_ii, indx_ii = traverser[i + 1]
                if (a.date().year + gap_lat_i == b.date().year
                        and b.date().year + 1 == c.date().year
                        and c.date().year + gap_lat_ii == d.date().year):
                    counter += 1
                    consecutive_test.append(True)

                else:
                    consecutive_test.append(False)

                if i + 1 == len(traverser) - 1:  # prints last line once reaches the end
                    print(f'{traverser[i][0]} and {traverser[i + 1][1]}')

            assert(single_file == False)
            assert(all(consecutive_test[:-1]))

def test_catalogue_traverser():
    pass

def test_check_grid_avail():

    DataFrameSubsetModel = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    model = list(DataFrameSubsetModel['source_id'].unique())[1] # 'CMCC-ESM2'
    DataFrameSubsetModel = DataFrameSubsetModel.loc[DataFrameSubsetModel['source_id'] == model]
    varlist = ['o2', 'so', 'thetao']

    dict_true = {'grid_label': ['gn', 'gr', 'gn', 'gr'],
                 'var_test': [[True, True, True],
                              [False, False, False],
                              [True, True, True],
                              [False, False, False]],
                 'variable_ids': [['o2', 'so', 'thetao'],
                                  ['o2', 'so', 'thetao'],
                                  ['o2', 'so', 'thetao'],
                                  ['o2', 'so', 'thetao']],
                 'has_all_variables': [True, False, True, False],
                 'run': ['piControl', 'piControl', 'historical', 'historical'],
                 'model': ['CMCC-ESM2', 'CMCC-ESM2', 'CMCC-ESM2', 'CMCC-ESM2']}

    # tests if all variables being queried have matching grids
    # example: Even though NorESM2-LM has thetao and so for the native grid, it does not have o2, then flag it and do not intake native grid files.
    # ...NorESM2-LM has all thetao, so, and o2 in the regular grid tho, so this should be included and processed further

    catch_state = True

    dict_test = {'grid_label': [],
            'var_test': [],
            'variable_ids': [],
            'has_all_variables': [],
            'run': [],
            'model': []}

    for run in ["piControl", "historical"] :
        DataFrameSubsetModel_run = DataFrameSubsetModel.loc[DataFrameSubsetModel['experiment_id'] == run]
        for grid in ["gn", "gr"]:
            DataFrameSubsetModel_grid = DataFrameSubsetModel_run.loc[DataFrameSubsetModel_run['grid_label'] == grid]  # subsetting for a grid type
            var_test = list(DataFrameSubsetModel_grid['variable_id'].unique())
            vart_test_ordered = set(var_test)
            varlist_ordered = set(varlist)

            var_test_final = [i==j for i, j in zip(sorted(list(varlist_ordered)), sorted(list(vart_test_ordered)))]
            if varlist_ordered == vart_test_ordered:
                catch_state = True
                varlist_ordered = sorted(list(varlist_ordered))

            else:
                missing_var = varlist_ordered - vart_test_ordered
                # padding for comparison between lists
                # make a list first
                vart_test_ordered = sorted(list(vart_test_ordered))
                varlist_ordered = sorted(list(varlist_ordered))

                string_flag = '!'
                for missing in missing_var:
                    idx = varlist_ordered.index(missing)
                    vart_test_ordered.insert(idx, missing + string_flag)

                # find indices of missing items and append them to specific positions followed by "!"
                catch_state = False
                var_test_final = [i == j for i, j in zip(varlist_ordered, vart_test_ordered)]

            dict_test['var_test'].append(var_test_final)
            dict_test['run'].append(run)
            dict_test['has_all_variables'].append(catch_state)
            dict_test['model'].append(model)
            dict_test['variable_ids'].append(varlist_ordered)
            dict_test['grid_label'].append(grid)

    assert (dict_test == dict_true)

def test_link_traverser():

    retain = 10 #number of rows to shrink test dataframe to

    #initialising ground truths
    test_downloadable = [True for item in range(0, retain-1)]
    test_downloadable.insert(0, False) # add first example of false

    #loading test dataframe
    DownloadableDF_tested = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    DownloadableDF_tested = DownloadableDF_tested[:retain] #just doing a subset for testing
    DownloadableDF_tested['Downloadable'] = None # set back to none for testing

    #changing first entry on purpose for testing
    str_original =  eval(DownloadableDF_tested.iloc[0]['HTTPServer'])
    str_original = ['https://httpbin.org/status/404' for item in str_original]
    DownloadableDF_tested.loc[0,'HTTPServer'] = str(str_original)

    # path ground thruth that is different on purpose so test will return false
    parts_test = Path(DownloadableDF_tested.iloc[0]['path'])
    path_test = Path('CMIP6', *list(parts_test.parts[1:]))

    ##############
    # First building an iterable to benefit from multiprocessing:
    iterable = []

    for idx in range(0, len(DownloadableDF_tested)):
        nested_url_list = [eval(DownloadableDF_tested.iloc[idx]['HTTPServer'])]  #change back to format that it is originally parsed
        flattened_list = [item for sublist in nested_url_list for item in sublist]
        file_id = DownloadableDF_tested.iloc[idx]['path']
        iterable.append((flattened_list, file_id))

    ## Complete - TODO build iterator with (file_id, [flattened list of urls]) to pass to multithreading function for the whole dataset
    with (ThreadPoolExecutor(max_workers=min(32, os.cpu_count() + 4)) as executor):
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

    ##this is where I stopped

    # reset index of DataFrame
    DownloadableDF_tested = DownloadableDF_tested.reset_index()

    state = []  # dummy array to store downloadable tests results - this will become a column in the dataframe
    # in the loop below item = collector[file_idx]
    for item in collector:
        if item[1][0] == False:  # this checks first value in collector[file_idx][1]
            print( f'File {os.path.basename(item[0][0][2])} not downloadable')  # look above for navigation onto the nested lists
        state.append(item[1][0])

    # appending new column to dataframe
    for idx, val in enumerate(state):
        DownloadableDF_tested.loc[idx, 'Downloadable'] = val

    local_paths = []  # dummy array to store local paths where results can be saved to - this will become a column in the dataframe
    path_start = 'CMIP6'
    for _ in DownloadableDF_tested['path']:
        _ = Path(_) #added line for unit testing so that when test dataframe is imported the functionality is the same
        pth = Path(path_start, *list(_.parts[3:]))  # build path only with those
        local_paths.append(pth)
    # appending new column to dataframe
    DownloadableDF_tested['local_path'] = None
    for idx, val in enumerate(local_paths):
        DownloadableDF_tested.loc[idx, 'local_path'] = val


    assert (state == test_downloadable)
    assert (DownloadableDF_tested['Downloadable'].tolist() == test_downloadable)
    assert (DownloadableDF_tested.loc[0, 'local_path'] != path_test)

def test_check_url_validity():

    links_working_test = [(False,
                          'https://httpbin.org/status/404',
                           'CMIP6/CMIP/CCCma/CanESM5/piControl/r1i1p1f1/Omon/o2/gn/v20190429/o2_Omon_CanESM5_piControl_r1i1p1f1_gn_520101-521012.nc'),
                          (True,
                           'http://crd-esgf-drc.ec.gc.ca/thredds/fileServer/esgC_dataroot/AR6/CMIP6/CMIP/CCCma/CanESM5/piControl/r1i1p1f1/Omon/o2/gn/v20190429/o2_Omon_CanESM5_piControl_r1i1p1f1_gn_520101-521012.nc',
                           'CMIP6/CMIP/CCCma/CanESM5/piControl/r1i1p1f1/Omon/o2/gn/v20190429/o2_Omon_CanESM5_piControl_r1i1p1f1_gn_520101-521012.nc')]


    DownloadableDF_tested = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    DownloadableDF_tested['Downloadable'] = None  # set back to none
    ##############
    # First building an iterable to benefit from multiprocessing:
    iterable = []

    for idx in range(0, len(DownloadableDF_tested)):
        nested_url_list = [
            eval(DownloadableDF_tested.iloc[idx]['HTTPServer'])]  # change back to format that it is originally parsed
        flattened_list = [item for sublist in nested_url_list for item in sublist]
        file_id = DownloadableDF_tested.iloc[idx]['path']
        iterable.append((flattened_list, file_id))

    ## this is the check url_validity implementation

    urls = iterable[0][0] # just doing the first item for testing
    file_ids = iterable[0][1]
    links_working = []
    file_downloadable = []

    for url in urls:

        if url == urls[0]: # dummy URL, returns HTTP 404 intentionally for test
            url = "https://httpbin.org/status/404"

        response = requests.get(url, stream=True)

        time.sleep(5)
        if response.status_code == 200:
            links_working.append((True, url, file_ids))
            break
        else:
            links_working.append((False, url, file_ids))
            continue

    if any(links_working):
        file_downloadable.append(True)
    else:
        file_downloadable.append(False)

    assert (links_working == links_working_test)
    assert (file_downloadable[0] == True)

def test_save_searched_tests():

    downloadpath = 'tests'
    df_downloadable_tested = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    df_name_dummy = df_downloadable_tested['variable_id'].unique().tolist()
    df_name = '_'.join(df_name_dummy)
    fname = os.path.join(downloadpath, 'DF_Downloadable_' + df_name)

    buffer = io.BytesIO()
    df_downloadable_tested.to_excel(buffer, index=False)
    data = buffer.getvalue()

    #assert that link traverser output and dataframe filtering return some data which are cached instead of written to file
    assert isinstance(data, bytes)
    assert len(data) > 0

    with pd.ExcelWriter(fname + '.xlsx', engine='openpyxl') as writer:
        df_downloadable_tested.to_excel(writer)
    assert (os.path.exists(fname + '.xlsx') == True)

    #remove dummy file after testing
    if os.path.isfile(fname + '.xlsx'):
        os.remove(fname + '.xlsx')

def test_import_ocean_std_names():
    root_proj = '.'
    for root, dirs, files in os.walk(root_proj):
        for name in files:
            if 'CMIP6_OceanVarNames.xlsx' in name:
                std_file_DF = pd.read_excel(os.path.join(root, name))
                std_names = std_file_DF['Variable Name'].to_list()

    assert std_names

#resume from here
def test_instantiate_logging_file():
    pass

## NOW functions inside main ocean var DL script

def test_test_download_speed():

    df_single_line = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    download_path = 'tests/tests_dl'

    url_list_str = df_single_line.iloc[0]['HTTPServer']
    url_list = ast.literal_eval(url_list_str)

    download_speeds = []

    for url in url_list:
        response = requests.get(url, stream=True)
        chunk_size = 2 ** 20  # 1Mb in bytes

        for chunk in response.iter_content(
                chunk_size=chunk_size):  # just do a dummy chunk download per url to test speed based on user's connection
            if chunk:
                download_speed = round((len(chunk) / (response.elapsed.microseconds)), 2)  # conversion to MBPS is numerically identical when data are in bytes per microsecond
                # print(f'Downloading speed is {download_speed} Mbps for url: {url}')
                break

        download_speeds.append(download_speed)

    # now return the url with fatest speed and use that
    # get indx of highest speed in the list
    fastest_url_idx = download_speeds.index(max(download_speeds))
    best_url = url_list[fastest_url_idx]

    assert best_url

def test_download_files():
    # loading testing dataframe variables
    DF_Downloadable_single_line = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    download_path = 'tests/tests_dl'
    file_path = DF_Downloadable_single_line.iloc[0]['local_path']  # complete - todo remove the first two levels from path to build the filename
    file_name = os.path.basename(file_path)
    outpath = os.path.join(download_path, os.path.dirname(file_path))
    file_fullname = os.path.join(outpath, file_name)
    content_length = DF_Downloadable_single_line.iloc[0]['size']

    if not os.path.isdir(outpath):
        os.makedirs(outpath)

    if DF_Downloadable_single_line.iloc[0]['Downloadable'] == True and not os.path.isfile(file_fullname):  # if downloadable and file has not been downloaded yet#
        # complete - TODO improvement change this call to func that retrieves the best url for the file in question

        url_list_str = DF_Downloadable_single_line.iloc[0]['HTTPServer']
        url_list = ast.literal_eval(url_list_str)

        download_speeds = []

        for url in url_list:
            response = requests.get(url, stream=True)
            chunk_size = 2 ** 20  # 1Mb in bytes

            for chunk in response.iter_content(
                    chunk_size=chunk_size):  # just do a dummy chunk download per url to test speed based on user's connection
                if chunk:
                    download_speed = round((len(chunk) / (response.elapsed.microseconds)),
                                           2)  # conversion to MBPS is numerically identical when data are in bytes per microsecond
                    # print(f'Downloading speed is {download_speed} Mbps for url: {url}')
                    break

            download_speeds.append(download_speed)

        # now return the url with fatest speed and use that
        # get indx of highest speed in the list
        fastest_url_idx = download_speeds.index(max(download_speeds))
        url_test = url_list[fastest_url_idx] #this is the fastest url

        print(f'Downloading file {file_name} to {outpath}')
        response = requests.get(url_test, stream=True)
        fraction_dl = 0.01  # Download only 1%
        max_bytes = int(content_length * fraction_dl)
        downloaded_bytes = 0
        chunk_size = 2**20  # 1 Mb

        with open(file_fullname, mode="wb") as file:
            pbar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, miniters=1,
                        total=max_bytes)  # Progress up to 10%
            pbar.set_description("Downloading « %s » (1%% test)" % file_name)
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:  # filter out keep-alive new chunks
                    pbar.update(len(chunk))
                    file.write(chunk)
                    downloaded_bytes += len(chunk)

                    if downloaded_bytes >= max_bytes:
                        print(f"\nStopped at {downloaded_bytes / (1024 ** 2):.1f} MB ({fraction_dl * 100:.0f}%)")
                        print(f"\nDone downloading a fraction of {fraction_dl} to {file_fullname}")
                        print('Download early-stopped on purpose to run testing on checksum verification')
                        break  # Stop downloading after 10%

        assert (os.path.isfile(file_fullname) == True) # check if file written to disk
        assert (os.path.getsize(file_fullname) == downloaded_bytes) # check if downloaded just the fraction

def test_verify_hash():

    #loading testing dataframe variables
    DF_Downloadable_single_line = pd.read_excel(os.path.join('tests', 'test_DF_Search.xlsx'))
    download_path = 'tests/tests_dl'
    file_path = DF_Downloadable_single_line.iloc[0]['local_path']
    file_name = os.path.basename(file_path)
    outpath = os.path.join(download_path, os.path.dirname(file_path))
    file_fullname = os.path.join(outpath, file_name)

    #checking intentional corruption
    if os.path.isfile(file_fullname):  # if file already exists
        # checksum part to test corruption
        print(f'File exisits at {file_fullname}')
        print(f"Checking for file integrity...\n")

        hash_source = DF_Downloadable_single_line.iloc[0]['checksum']

        # Create a SHA-256 hash object.
        sha256_hash = hashlib.sha256()
        # Open the file in binary mode for reading (rb).
        with open(file_fullname, "rb") as file:
            # Read the file in 64KB chunks to efficiently handle large files.
            while True:
                data = file.read(65536)  # Read the file in 64KB chunks.
                if not data:
                    break
                # Update the hash object with the data read from the file.
                sha256_hash.update(data)
        # Return the hexadecimal representation of the calculated hash.
        file_hash = sha256_hash.hexdigest()

        hash_test = (file_hash == hash_source)  # if returns TRUE then file is not corrupted, but file corrupted on purpose for testing
        if hash_test == False:
            print(f'File corrupted intentionally at {file_fullname}')
    assert (hash_test == False)

## NOW functions inside main cell measure DL script
def test_import_ocean_var_names():
    DL_ocean_var_path = 'tests'
    DF_master = pd.DataFrame()
    # import DFs
    for file in os.listdir(DL_ocean_var_path):
        if 'test_DF_Search' in file and file.endswith(".xlsx") and not ('areacello' in file or 'volcello' in file):
            df_filename = os.path.join(DL_ocean_var_path, file)
            DF_dummy = pd.read_excel(df_filename, engine='openpyxl')
            DF_master = pd.concat([DF_master, DF_dummy])

    assert (DF_master.empty == False)

def test_varcell_prepare_df():

    DL_ocean_var_path = 'tests'
    var = 'areacello'
    download_path = DL_ocean_var_path + '/tests_dl'
    DF_master = pd.DataFrame()

    # import DFs
    for file in os.listdir(DL_ocean_var_path):
        if 'test_DF_Search' in file and file.endswith(".xlsx") and not ('areacello' in file or 'volcello' in file):
            df_filename = os.path.join(DL_ocean_var_path, file)
            DF_dummy = pd.read_excel(df_filename, engine='openpyxl')
            DF_master = pd.concat([DF_master, DF_dummy])

    #now filtering just the first 3 entries
    DF_master = DF_master.loc[0:2]
    var_id = DF_master['variable_id'].unique()

    print(f"Dataframe for variables {var_id} imported.")
    models_target = DF_master['source_id'].unique().tolist()

    print(f"Catalogue search started...")
    # scrape to see which ones to include
    cat = ESGFCatalog().search(
        project='CMIP6',
        # activity_drs=['CMIP'],
        # experiment_id=['piControl', 'historical'],
        source_id = list(models_target)[0],
        variable_id = var,
    )
    models_cellmeasure = cat.df['source_id'].unique().sort()

    # dictionary structure containing all the urls, SHA256 hashes to enable serialised download
    info = cat.infos_to_dict(quiet=False)
    DataFrameSearch = pd.DataFrame.from_dict(info['https'])
    DF_cellmeasure = append_cols(PandasDataFrame=DataFrameSearch)

    test_list = [model in DF_cellmeasure['source_id'].unique().tolist() for model in models_target]
    for test, model in zip(test_list, models_target):
        print(f"Found {var} for model {model}? {test}")

    print('Summary of test was:')
    if all(test_list):
        print(f"Found cell variable {var} for all models shortlisted for var {var_id}:")
    else:
        res = [i for i, val in enumerate(test_list) if not val]
        for idx in res:
            print(f"Cell variable {var} for model {models_target[idx]} not found.")


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
                    print(f"\nFound possible matches for {target_key} in cell measure dataframe for model {model}.")
                    print(f"Indices for files in cell measure dataframe are {matches}")
                    model_found.append(model)

                    ##now check if all shortlisted file sizes are the same
                    DF_cellmeasure_shortlisted = DF_cellmeasure[DF_cellmeasure.index.isin(matches)]
                    DF_cellmeasure_selected = DF_cellmeasure_shortlisted.iloc[
                        [0]]  # copy first line to initiate dataframe that will be concatenated

                    # account for cases where file size values are different and shrink dataframe to shortlist one instance of each option and download both to check later
                    vals = DF_cellmeasure_shortlisted['size'].unique().tolist()
                    vals.sort()

                    if len(vals) != 1:
                        print(
                            f"Model {model} has duplicate {var} files with {len(vals)} different sizes.Registering for later inspection.\n")
                    else:
                        print(f"Model {model} has no duplicate {var} files.\n")

                    processed = []
                    for val in vals:
                        if val not in processed:
                            for idx in range(0, len(DF_cellmeasure_shortlisted)):
                                if DF_cellmeasure_shortlisted.iloc[idx]['size'] == val:
                                    DF_cellmeasure_selected = pd.concat(
                                        [DF_cellmeasure_selected, DF_cellmeasure_shortlisted.iloc[[idx]]])
                                    # print(f"Processed {val}")
                                    break  # break from checking size loop as only a single copy is needed to be appended
                            processed.append(val)

                    # getting all but first entry, which was copied to initialise the dataframe
                    DF_cellmeasure_selected = DF_cellmeasure_selected.iloc[1:]

                    ##now appending results back to filtered dataframe
                    DF_cellmeasure_relaxed_regex = pd.concat([DF_cellmeasure_relaxed_regex, DF_cellmeasure_selected])

                    assert (DF_cellmeasure_relaxed_regex.empty == False) #check if cell measures have been found for each file

                    # TODO complete subset save a subset dataframe per model for the cell measure inside the model folder to check in the future
                    short_path = os.path.join(download_path, 'CMIP6', model, var)
                    if not os.path.exists(short_path):
                        os.makedirs(short_path)
                    DF_cellmeasure_selected.to_excel(os.path.join(short_path, model + "_" + var + ".xlsx"))

    # checks if individual cell measure spreadsheet has been saved under the model folder
    assert (os.path.isfile(os.path.join(short_path, model + "_" + var + ".xlsx")) == True)

