
"""
Loads Catalogue Dataframes for outputs of interest and downloads in parallel to user-specified path.
Once downloaded, it checks for file integrity and re-downloads if corrupted.

"""

import os.path
import numpy as np
from precog_esgf_intake.scripts.intake_UtilFuncs import *
from multiprocessing.pool import ThreadPool
import hashlib
from pathlib import Path
import sys
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

def verify_hash(downloaded_file, expected_hash):
    # Calculate the hash of the downloaded file.
    calculated_hash = calculate_hash(downloaded_file)
    # Compare the calculated hash with the expected hash and return the result.
    return calculated_hash == expected_hash

def calculate_hash(file_path):
    # Create a SHA-256 hash object.
    sha256_hash = hashlib.sha256()
    # Open the file in binary mode for reading (rb).
    with open(file_path, "rb") as file:
        # Read the file in 64KB chunks to efficiently handle large files.
        while True:
            data = file.read(65536)  # Read the file in 64KB chunks.
            if not data:
                break
            # Update the hash object with the data read from the file.
            sha256_hash.update(data)
    # Return the hexadecimal representation of the calculated hash.
    return sha256_hash.hexdigest()

def dwnld_speed_test_browser_like(df_single_line, session=None, max_probe_bytes=2 ** 18):

    if session is None:
        session = requests.Session()
        # Rotate User-Agents
        agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        session.headers.update({'User-Agent': random.choice(agents)})

        # Retry strategy
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)


    url_list_str = df_single_line.iloc[0]['HTTPServer']  # Complete - TODO improvement change this call to func that retrieves the best url for the file in question
    url_list = ast.literal_eval(url_list_str)
    url_list = list(set(url_list)) #this removes repeated entries
    download_speeds = []

    for i, url in enumerate(url_list):
        # Complete TODO - check if no timeout error is raised with the url and if so remove it from the list of urls for that file and test the next best url until one works.
        try:
            resp = session.get(
                url, stream=True, timeout=(15, 45),  # Longer timeouts
                headers={'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9'},
                allow_redirects=True
            )

            if resp.status_code == 200:  # Accept only full 200 (ESGF ignores 206 often)
                chunk_size = max_probe_bytes
                total_bytes = 0
                elapsed_start = time.time()

                chunk_count = 0
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        total_bytes += len(chunk)
                        chunk_count += 1
                        if total_bytes >= max_probe_bytes or chunk_count >= 2:  # 1-2 full chunks
                            break

                elapsed = time.time() - elapsed_start
                speed = round((total_bytes / elapsed) / 1e6, 2) if elapsed else 0
                download_speeds.append(speed)
            else:
                download_speeds.append(-1 if resp.status_code == 404 else 0)

        except Exception as e:
            download_speeds.append(0)

        # Rate limit: 2-5s delay between URLs (per file)
        if i < len(url_list) - 1:
            time.sleep(random.uniform(2, 4))

    # Close session if we created it
    if session and len(url_list) > 0:
        session.close()

    return {'urls': url_list, 'speeds': download_speeds}

def download_files(DF_Downloadable_single_line, download_path, download_logger):

    file_path = DF_Downloadable_single_line.iloc[0]['local_path']  # complete - TODO remove the first two levels from path to build the filename
    file_name = os.path.basename(file_path)
    outpath = os.path.join(download_path, os.path.dirname(file_path))
    file_fullname = os.path.join(outpath, file_name)

    content_length = DF_Downloadable_single_line.iloc[0]['size']

    if not os.path.isdir(outpath):
        os.makedirs(outpath, exist_ok=True)# creates directory tree structure

    # complete TODO - change this call to func that retrieves the best url for the file in question
    speed_test_dict = dwnld_speed_test_browser_like(DF_Downloadable_single_line)
    sorted_indices = np.argsort(speed_test_dict['speeds'])[::-1]
    sorted_urls = [speed_test_dict['urls'][i] for i in sorted_indices]

    if DF_Downloadable_single_line.iloc[0]['Downloadable'] == True and not os.path.isfile(file_fullname):  # if downloadable and file has not been downloaded yet#

        download_logger.info(text_align(f"Starting download for file: {file_name}\n"))
        try_download(sorted_urls, file_fullname, file_name, content_length, download_logger)

    elif os.path.isfile(file_fullname):  # if file already exists
        # checksum part to test corruption
        download_logger.info(text_align(f'File exists at {file_fullname}'))
        download_logger.info(f"Checking for file integrity...")

        hash_source = DF_Downloadable_single_line.iloc[0]['checksum']
        hash_test = verify_hash(file_fullname, hash_source)  # if returns TRUE then file is not corrupted

        if hash_test == False:  # if it exists but hash test showed corruption
            download_logger.info(text_align(f"File checksum indicates corruption. Downloading again to: {download_path}\n"))

            try_download(sorted_urls, file_fullname, file_name, content_length, download_logger)

        elif hash_test == True:
            download_logger.info(text_align(f"File is intact and already downloaded to {file_fullname}\n"))

def try_download(sorted_urls, file_fullname, file_name, content_length, download_logger, session=None):

    if session is None:
        session = requests.Session()
        # Rotate User-Agents
        agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        session.headers.update({'User-Agent': random.choice(agents)})

        # Retry strategy
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

    for i, url_test in enumerate(sorted_urls):
        try:
            response = session.get(
                url_test, stream=True, timeout=(15, 45),  # Longer timeouts
                headers={'Accept': '*/*', 'Accept-Language': 'en-US,en;q=0.9'},
                allow_redirects=True
            )

            with open(file_fullname, mode="wb") as file:
                pbar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, miniters=1,
                            total=content_length)  # shows pbar in Kilobytes
                pbar.set_description("Downloading « %s »" % file_name)
                for chunk in response.iter_content(chunk_size=2**20):
                    if chunk:  # filter out keep-alive new chunks
                        pbar.update(len(chunk))
                        file.write(chunk)
            break


        except requests.ConnectionError as e:  # this catches error when server hangs up mid-ring because it thinks we are a bot
            download_logger.debug(text_align(f"Critical error with {url_test}: {e}"))
            download_logger.debug("Trying second best url...\n")

        # Rate limit: 2-5s delay between URLs (per file)
        if i < len(sorted_urls) - 1:
            time.sleep(random.uniform(2, 4))

    else:# when all options are exhausted
        download_logger.debug(text_align(f"Unable to automatically download {file_name}."))
        download_logger.debug(f"All url options exhausted.Please check ESGF nodes manually at:")
        download_logger.debug('##########')
        download_logger.debug(text_align("\n".join([f"{url}" for url in sorted_urls])))
        download_logger.debug('##########\n')

def download_non_parallel_files(df, download_path, logger):
    """
    Reads the E dataframe and downloads files from HTTPServer URLs where DownloadableParallel == False.

    Args:
    excel_path (str): Path to the Excel file.
    download_dir (str): Directory to save downloads (created if missing).
    """
    # Filter rows where DownloadableParallel == False
    filtered_df = df[df['DownloadableParallel'] == False].copy()

    if filtered_df.empty:
        logger.info("No rows found with DownloadableParallel == False.")
        return filtered_df

    # Create download directory
    os.makedirs(download_path, exist_ok=True)

    downloaded = 0
    for idx, row in filtered_df.iterrows():
        # Parse the HTTPServer string as a list (it's a string representation of a list)
        url_list_str = row['HTTPServer']
        urls = ast.literal_eval(url_list_str)
        unique_urls = list(set(urls))  # Remove duplicates

        # get filename full path
        filename = os.path.basename(df.iloc[idx]['local_path'])
        output_path = os.path.join(download_path, df.iloc[idx]['local_path'])

        for url in unique_urls:
            url = url.replace("http://", "https://") if url.startswith("http://") else url

            # Skip if already exists
            if os.path.exists(output_path) and calculate_hash(output_path) == df.iloc[idx]['checksum']:
                logger.info(f"Skipping {filename} (already exists and is intact)")
                filtered_df.at[idx,'DownloadedToDisk'] = True
                continue

            else:
                # Run wget subprocess
                cmd = ['wget', '-O', output_path, url]
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    logger.info(f"Downloaded: {filename}")
                    filtered_df.at[idx,'DownloadedToDisk'] = True
                    downloaded += 1
                except subprocess.CalledProcessError as e:
                    logger.info(f"Failed to download {url}: {e.stderr}")
                    filtered_df.at[idx,'DownloadedToDisk'] = False
                    continue

    logger.info(f"Serialised download sweep complete. {downloaded} new files saved to {download_path}.")

    # returns the filtered DF with the results of the download sweep
    return filtered_df



#############################################

if __name__=="__main__":

    print_precog_header()

    ### Defining paths and loading dataframes
    download_path = input("Define the download path. Either type path or drag desired download folder onto this terminal window:")
    download_path = Path(download_path.strip(" ")) #strip added as dragging onto terminal adds a trailing 'space'

    df_filename = input("Now either drag onto terminal or type path to Dataframe with the Filtered ESGF search results desired:")
    df_filename = Path(df_filename.strip(" ")).name #strip added as dragging onto terminal adds a trailing 'space'

    # logging file: append exception catching from within download_files function
    today = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dl_name = df_filename.split('DF_Downloadable_')[1].split('.xlsx')[0]
    log_dl_path = os.path.join(download_path, f"ESGF_DownloadLog_{log_dl_name}_{today}.txt")
    logger_dld = instantiate_logging_file(log_dl_path, logger_name=str(log_dl_name)) # start the logger

    logger_dld.info('Checking if Dataframe is readable')
    logger_dld.info(os.path.isfile(os.path.join(download_path, df_filename)))
    logger_dld.info(f'Importing Dataframe {df_filename}')

    # ### Defining paths and loading dataframes using Tkinter system GUI window
    # print('Select Download path on the open window')
    # download_path = tk.filedialog.askdirectory(
    #                                         title='Select path where files will be downloaded to',
    #                                         initialdir=os.getcwd())
    #
    # df_filename = tk.filedialog.askopenfilename(
    #                                         title='Select Dataframe with the Filtered ESGF search results',
    #                                         initialdir=os.getcwd(),
    #                                         filetypes=(('CSV','*.csv'), ('Excel', '*.xlsx')),
    #                                         )
    # df_filename = Path(df_filename).name

    # Load filtered search 'Downloadable' Dataframe prompting user for space required
    df_downloadable = pd.read_excel(os.path.join(download_path, df_filename))

    ## NOW ONTO DOWNLOADING FILES
    # prompt for user input
    logger_dld.info(f'There are {len(df_downloadable)} files totalling {(sum(df_downloadable['size'])/1e9):.2f} Gb for variable(s) {df_downloadable['variable_id'].unique().tolist()}')
    user_input = input("Do you want to continue to downloads? (yes/no): ")
    user_input = user_input.strip(" ")

    if user_input.lower() in ["yes", "y"]:
        logger_dld.info(f'User said {user_input.lower()}')
        logger_dld.info("Continuing...\n")

        #parallelizing download only for mirrors that are more permissive
        df_downloadable_fast = df_downloadable[df_downloadable['DownloadableParallel']==True] # filter DF by DownloadableParallel column flags
        iterable_dwnld = []
        for i in range(0, len(df_downloadable_fast)):
            # building_iterable
            df_single = df_downloadable_fast.iloc[[i]]
            iterable_dwnld.append(
                (df_single, download_path, logger_dld))  # this is the iterable being passed to the download function with 2 args

        with  ThreadPool(processes=2) as pool: #still limit this to two concurrent download to not overload
            pool.starmap(download_files, iterable_dwnld) #starmap unpacks the iterable args to function

        #check if all files were downloaded to destination and append file status to dataframe
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


    else:
        logger_dld.info("Exiting...\n")

    #Motivanional quote
    print_precog_footer()
    print(f'Downloaded ESM outputs should have been saved at {os.path.join(download_path, 'CMIP6')}')
    print('Check logs and whether you got the data. Now go be amazing!')


#############################################
########### NEXT STEPS ####################
# COMPLETE TODO - New program : new catalogue search to retrieve ocean cell measures for the models that have been shortlisted
# TODO - New program : find models after screening for pi and Historical which have forward branching simulations available in for example 'ScenarioMIP' activities
