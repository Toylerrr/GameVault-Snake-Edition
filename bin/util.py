import base64
import requests
import configparser
import os
import json
from PIL import Image,ImageDraw
from io import BytesIO
from pySmartDL import SmartDL
import patoolib
import threading
from platformdirs import *
import logging
import platform
import shutil
import keyring



#___________NEW CODE___________
appname = 'GameVault-Snake Edition'
appauthor = 'Toylerrr'
settings_file_name = 'settings.ini'
settings_location = user_data_dir(appname, appauthor)
settings_file = os.path.join(settings_location, settings_file_name)


# Ensure settings directory exists
os.makedirs(settings_location, exist_ok=True)

# Check if settings file exists
if not os.path.exists(settings_file):
    # Create ConfigParser instance
    config = configparser.ConfigParser()

    # Set default values
    config['SETTINGS'] = {
        'username': '',
        'install_location': '',
        'url': '',
        'apperance': 'System',
        'theme': 'blue',
        'debug': 'False'
    }

    # Write the default configuration to the file
    with open(settings_file, 'w') as configfile:
        config.write(configfile)
else:
    # Read configuration from file
    config = configparser.ConfigParser()
    config.read(settings_file)

if config['SETTINGS'].get('debug') == 'True':
    logging.basicConfig(level=logging.DEBUG)

# Get values from config
username = config['SETTINGS'].get('username')
install_location = config['SETTINGS'].get('install_location')
url = config['SETTINGS'].get('url')
# logging.debug(url)



CACHE_DIR = f"{settings_location}/cache"                             #This is where we will store the 
CACHE_FILE = f"{CACHE_DIR}/cached_games.json"               #This is all the games in one file
os.makedirs(settings_location, exist_ok=True) 




#___________END NEW CODE___________

def is_online():
    try:
        response = requests.get(url)
        if response.status_code == 200:
            logging.debug("ONLINE")
            return True
    except Exception:
        logging.debug("OFFLINE")
        return False
    
online_status = is_online()

def check_url_health(passedurl):
    try:
        response = requests.get(f'{passedurl}/api/health')
        if response.status_code == 200:
            logging.debug("CODE 200 on url health check")
            json_data = response.json()
            if "status" in json_data and json_data["status"] == "HEALTHY":
                return True
    except Exception as e:
        logging.debug(f"An error occurred: {e}")
    
    return False

def save_cache(gid, data):
    cache_file = os.path.join(CACHE_DIR, f"{gid}.json")
    with open(cache_file, "w") as file:
        json.dump(data, file)

def load_cache(gid):
    cache_file = os.path.join(CACHE_DIR, f"{gid}.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r") as file:
            return json.load(file)
    return None

def clear_cache():
    # Check if the cache directory exists
    if os.path.exists(CACHE_DIR):
        # Iterate over all files and subdirectories in the cache directory
        for root, dirs, files in os.walk(CACHE_DIR, topdown=False):
            # Remove all files in the current directory
            for filename in files:
                file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                except Exception as e:
                    logging.debug(f"Failed to remove {file_path}: {e}")
            # Remove the current subdirectory itself
            for dirname in dirs:
                dir_path = os.path.join(root, dirname)
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    logging.debug(f"Failed to remove {dir_path}: {e}")
        # Print a message indicating that the cache was cleared successfully
        logging.debug("Cache cleared successfully.")
    else:
        # Print a message if the cache directory does not exist
        logging.debug("Cache directory does not exist. Nothing to clear.")

def fetch_game_info(username, password, gid):
    # Check if the response is already in the cache
    cached_data = load_cache(gid)
    if cached_data:
        logging.debug(f"Fetching from game info from cache...{gid}")
        return cached_data

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    url = f'{config['SETTINGS'].get('url')}/api/games/{gid}'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Basic {encoded_credentials}'
    }
    params = {}

    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Cache the response
        save_cache(gid, data)
        return data
    else:
        logging.debug("Failed to fetch game info. Status code:", response.status_code)
        return None


def add_gradient(username, password, gid):
    logging.debug("radient function running")
    # Check if the image with gradient already exists in cache
    output_folder = os.path.join(CACHE_DIR, str(gid))
    output_path = os.path.join(output_folder, f"{gid}_with_gradient.png")
    
    if os.path.exists(output_path):
        logging.debug("Gradient already added to image. Returning cached version.")
        return output_path
    
    # Open the original image
    logging.debug("Gradient function: Opening image...")
    image_path = get_image(username, password, gid, boxart=False)
    if image_path is None:
        logging.debug("Failed to fetch the image.")
        return None

    image = Image.open(image_path).convert("RGBA")
    width, height = image.size
    
    # Calculate the alpha gradient
    start_gradient_y = height // 3  # Start the gradient about one-third down the image
    for y in range(height):
        if y >= start_gradient_y:
            # Calculate the alpha value based on the distance from the start of the gradient
            alpha = int(255 * (1 - (y - start_gradient_y) / (height - start_gradient_y)) ** 5)  # Adjust the exponent for a more rapid decrease
            
            # Set a minimum threshold for the alpha value
            min_alpha = 10  # Adjust as needed
            alpha = max(alpha, min_alpha)  # Ensure the alpha value doesn't fall below the threshold
        else:
            alpha = 255  # Full opacity for the top portion of the image
        
        for x in range(width):
            r, g, b, _ = image.getpixel((x, y))
            image.putpixel((x, y), (r, g, b, alpha))
    
    # Save the resulting image
    os.makedirs(output_folder, exist_ok=True)
    image.save(output_path)
    logging.debug(f"Gradient added to cache: {output_path}")
    return output_path


# def download_game(username, password, gid, force_redownload=False):
#     encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
#     url = f'{URL}/api/games/{gid}/download'
#     installfolder = config['SETTINGS'].get('install_location')
#     path = fetch_game_info(username, password, gid)
#     destination = f"{installfolder}/{gid}/download/{os.path.basename(path['file_path'])}"
    
#     # Check if the file already exists and force_redownload is False
#     if not force_redownload and os.path.exists(destination):
#         print("Game already downloaded:", destination)
#         return destination
    
#     request_args = {"headers": {"Authorization": f'Basic {encoded_credentials}'}}
#     downloader = SmartDL(url, destination, request_args=request_args)
#     # threading.Thread(target=downloader.start, daemon=True).start()
#     downloader.start()  # Starts the downloading process
    
#     if downloader.isSuccessful():
#         print("Downloaded successfully:", downloader.get_dest())
#         return downloader.get_dest()
#     else:
#         print("Download failed:", downloader.get_errors())
#         return None


def install_game(gid):
    foldername = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{config['SETTINGS'].get('install_location')}/{gid}/{os.path.splitext(os.path.basename(foldername['file_path']))[0]}"
    gamezip = f"{config['SETTINGS'].get('install_location')}/{gid}/download/{os.path.basename(foldername['file_path'])}"
    patoolib.extract_archive(gamezip , outdir=destination)
    installfolder = config['SETTINGS'].get('install_location')
    open(f"{installfolder}/{gid}/.installed", 'w').close()
    logging.debug("UNZIPPED GAME")

def is_downloaded(gid):
    installfolder = config['SETTINGS'].get('install_location')
    path = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{installfolder}/{gid}/download/{os.path.basename(path['file_path'])}"
    return os.path.exists(destination)

def is_installed(gid):
    installfolder = config['SETTINGS'].get('install_location')
    path = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{installfolder}/{gid}/.installed"
    logging.debug(f"Checking if {destination} exists...")
    return os.path.exists(destination)

def get_exes_paths(gid):
    foldername = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{config['SETTINGS'].get('install_location')}/{gid}/{os.path.splitext(os.path.basename(foldername['file_path']))[0]}"
    exes = []
    for root, dirs, files in os.walk(destination):
        for filename in files:
            if filename.endswith(".exe"):
                exes.append(os.path.join(root, filename))
    return exes
def get_exes(gid):
    foldername = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{config['SETTINGS'].get('install_location')}/{gid}/{os.path.splitext(os.path.basename(foldername['file_path']))[0]}"
    exes = []
    for root, dirs, files in os.walk(destination):
        for filename in files:
            if filename.endswith(".exe"):
                exes.append(filename)
    return exes

def save_exe_selection(gid, exe):
    installfolder = config['SETTINGS'].get('install_location')
    path = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{installfolder}/{gid}/.installed"
    with open(destination, 'w') as f:
        f.write(exe)

def get_exe_selection(gid):
    installfolder = config['SETTINGS'].get('install_location')
    destination = f"{installfolder}/{gid}/.installed"
    with open(destination, 'r') as f:
        return f.read()

#THIS NEEDS A REWORK TO CHECK IF CACHE IS DIFFRENT THEN THE NEW DOWNLOAD
# def fetch_game_titles(username, password):
#     # Try to load cached data
#     if os.path.exists(CACHE_FILE):
#         with open(CACHE_FILE, "r") as file:
#             cached_data = json.load(file)
#         logging.debug("Using cached game titles.")
#         return cached_data

#     encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
#     # url = f'{config['SETTINGS'].get('url')}/api/games'
#     headers = {
#         'accept': 'application/json',
#         'Authorization': f'Basic {encoded_credentials}'
#     }
#     params = {'sortBy': 'title:ASC'}

#     response = requests.get(f'{config['SETTINGS'].get('url')}/api/games', params=params, headers=headers)

#     if response.status_code == 200:
#         data = response.json()
#         games = data['data']
        
#         # Cache the fetched data
#         with open(CACHE_FILE, "w") as file:
#             json.dump(games, file)

#         return games
#     else:
#         logging.debug("Failed to fetch game titles. Status code:", response.status_code)
#         return None

def get_disk_usage(path):
    usage = shutil.disk_usage(path)
    usage_gb = usage.used / (1024 * 1024 * 1024)
    return usage_gb

def get_disk_free(path):
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024 * 1024 * 1024)
    return free_gb
def get_disk_total(path):
    usage = shutil.disk_usage(path)
    total_gb = usage.total / (1024 * 1024 * 1024)
    return total_gb

# def fetch_game_titles(username, password):
#     # Try to load cached data
#     cached_data = {}
#     if os.path.exists(CACHE_FILE):
#         with open(CACHE_FILE, "r") as file:
#             cached_data = json.load(file)
#         logging.debug("Using cached game titles.")

#     encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
#     headers = {
#         'accept': 'application/json',
#         'Authorization': f'Basic {encoded_credentials}'
#     }
#     params = {'sortBy': 'title:ASC'}

#     response = requests.get(f'{config["SETTINGS"].get("url")}/api/games', params=params, headers=headers)

#     if response.status_code == 200:
#         data = response.json()
#         games = data['data']
        
#         # Check if there's a difference between current and cached data
#         if games != cached_data:
#             # Update the cached data
#             with open(CACHE_FILE, "w") as file:
#                 json.dump(games, file)
#             logging.debug("Cached game titles updated.")

#         return games
#     else:
#         logging.debug("Failed to fetch game titles. Status code:", response.status_code)
#         return None
    
def get_image(username, password, gid, boxart=False):

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

    cache_folder = os.path.join(CACHE_DIR, str(gid))
    os.makedirs(cache_folder, exist_ok=True)

    if boxart:
        cache_path = os.path.join(cache_folder, 'box_art_image.jpg')
        if os.path.exists(cache_path):
            # If box art image is cached, return the file path
            return cache_path

        # Fetch game information to get box art image URL
        game_info = fetch_game_info(username, password, gid)
        box_image_id = game_info['box_image'].get('id')

        headers = {
            'accept': 'application/json',
            'Authorization': f'Basic {encoded_credentials}'
        }
        params = {}

        response = requests.get(config['SETTINGS'].get('url') + f'/api/images/{box_image_id}',params=params, headers=headers)
        if response.status_code == 200:
            image_bytes = BytesIO(response.content)
            image = Image.open(image_bytes)

            # Convert image to RGB mode
            if image.mode == 'RGBA':
                image = image.convert('RGB')

            # Cache the image
            image.save(cache_path)
            print(cache_path)
            return cache_path
        else:
            print(f"Failed to retrieve box art image. Status code: {response.status_code}")
            return "bin\\img\\not_found.jpg"
        

        

    else:
        cache_path = os.path.join(cache_folder, 'BG_image.jpg')
        if os.path.exists(cache_path):
            # If box art image is cached, return the file path
            print(f"{cache_path}fetching from cache")
            return cache_path

        # Fetch game information to get box art image URL
        game_info = fetch_game_info(username, password, gid)
        if game_info and 'background_image' in game_info:
            box_image_url = game_info['background_image'].get('source')
            if box_image_url:
                try:
                    response = requests.get(box_image_url)
                    if response.status_code == 200:
                        image_bytes = BytesIO(response.content)
                        image = Image.open(image_bytes)

                        # Convert image to RGB mode
                        if image.mode == 'RGBA':
                            image = image.convert('RGB')

                        # Cache the image
                        image.save(cache_path)

                        return cache_path
                    else:
                        print(f"Failed to retrieve box art image. Status code: {response.status_code}")
                except Exception as e:
                    print(f"An error occurred while fetching box art image: {e}")
            else:
                print("Box art image URL not found in game information.")
        else:
            print("Box art image information not found in game data.")
        return None

#UPDATED FUNCTIONS
# def fetch_game_titles(username, password, online_status=True):
#     cached_data = {}
#     encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

#     if os.path.exists(CACHE_FILE):
#         with open(CACHE_FILE, "r") as file:
#             cached_data = json.load(file)
#         logging.debug("Using cached game titles.")

#     if not online_status:
#         logging.debug("GV Client Offline. Using cached game titles.")
#         return cached_data

#     # API Call
#     headers = {'accept': 'application/json', 'Authorization': f'Basic {encoded_credentials}'}
#     params = {'sortBy': 'title:ASC'}
#     response = requests.get(config["SETTINGS"].get("url") + "/api/games", params=params, headers=headers)

#     if response.status_code == 200:
#         data = response.json().get('data', [])

#         if data != cached_data:
#             with open(CACHE_FILE, "w") as file:
#                 json.dump(data, file)
#             logging.debug("Cached game titles updated.")

#         return data
#     else:
#         logging.error(f"Failed to fetch game titles. Status code: {response.status_code}")
#         return []

# def fetch_game_info(username, password, gid):
#     # Check if the response is already in the cache
#     cached_data = load_cache(gid)


#     if online_status == False:
#         logging.debug("GV Client Offline. Using cached game titles.")
#         return cached_data
#     elif online_status == True:
#         encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
#         url = f'{config['SETTINGS'].get('url')}/api/games/{gid}'
#         headers = {
#             'accept': 'application/json',
#             'Authorization': f'Basic {encoded_credentials}'
#         }
#         params = {}

#         response = requests.get(url, params=params, headers=headers)
#         if response.status_code == 200:
#             data = response.json()
#             # Cache the response
#             if data != cached_data:
#                 save_cache(gid, data)
#                 logging.debug(f"Cached game data for {gid} updated.")
#             return data
#         else:
#             logging.debug("Failed to fetch game info. Status code:", response.status_code)
#             return cached_data




# # test_fetch = fetch_game_info(username, keyring.get_password("GameVault-Snake", username),1)
# fetch_game_info(username, keyring.get_password("GameVault-Snake", username),1)

# # print(test_fetch)



def fetch_game_titles(username, password, online_status=True):
    cached_data = {}
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()

    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            cached_data = json.load(file)
        logging.debug("GV Client Online.Using cached game titles.")

    if not online_status:
        logging.debug("GV Client Offline. Using cached game titles.")
        return cached_data

    # API Call
    headers = {'accept': 'application/json', 'Authorization': f'Basic {encoded_credentials}'}
    params = {'sortBy': 'title:ASC'}
    try:
        response = requests.get(config["SETTINGS"].get("url") + "/api/games", params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for non-200 status codes
        data = response.json().get('data', [])
        if data != cached_data:
            with open(CACHE_FILE, "w") as file:
                json.dump(data, file)
            logging.debug("Cached game titles updated.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch game titles: {e}")
        return cached_data