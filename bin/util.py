import base64
import requests
import configparser
import os
import json
from PIL import Image
from io import BytesIO
from platformdirs import *
import logging
import shutil
import keyring
import sqlite3
import subprocess
# import py7zr
import zipfile
import notifypy
from notifypy import Notify
import functools
notifypy.Notify._selected_notification_system = functools.partial(notifypy.Notify._selected_notification_system, override_windows_version_detection=True)
import mimetypes
import customtkinter
from pypdl import Pypdl
import aiohttp




#___________Main Settings___________
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

# Define the path for the SQLite database file
DB_PATH = os.path.join(CACHE_DIR, "cache.db")
#___________END Main Settings___________

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

# Function to initialize the database and create the cache table if it doesn't exist
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                gid TEXT PRIMARY KEY,
                data TEXT
            )
        ''')
        conn.commit()

# Function to save cache data to the SQLite database
def save_cache(gid, data):
    init_db()  # Ensure the database is initialized
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO cache (gid, data) VALUES (?, ?)
        ''', (gid, json.dumps(data)))
        conn.commit()

# Function to load cache data from the SQLite database
def load_cache(gid):
    init_db()  # Ensure the database is initialized
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT data FROM cache WHERE gid = ?', (gid,))
        result = cursor.fetchone()
        if result:
            return json.loads(result[0])
        return None

# Function to clear the cache from the SQLite database
def clear_cache():
    init_db()  # Ensure the database is initialized
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cache')
        conn.commit()
    logging.debug("Cache cleared successfully.")



def unzip_game(gid):
    foldername = fetch_game_info("NULL", "NULL", gid)  # Assuming this fetches the game info
    game_name = foldername['title']
    logging.debug(f"Game name: {game_name}")
    
    install_location = config['SETTINGS'].get('install_location')
    destination = os.path.join(install_location, f"Installations/({gid}){game_name}/Files")
    logging.debug(f"Destination: {destination}")
    
    # Create the destination directory if it doesn't exist
    os.makedirs(destination, exist_ok=True)
    logging.debug(f"Created destination directory: {destination}")
    
    downloaded_file = is_downloaded(gid, file_path=True)
    downloaded_file = os.path.normpath(downloaded_file)  # Sanitize the file path using normpath
    logging.debug(f"Downloaded file: {downloaded_file}")
    
    if os.path.isfile(downloaded_file) and zipfile.is_zipfile(downloaded_file):
        try:
            with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                zip_ref.extractall(destination)
            logging.debug("UNZIPPED GAME")
        except Exception as e:
            logging.error(f"Error extracting {downloaded_file}: {e}")
            # Cleanup if extraction fails
            logging.debug(f"Cleaning up {destination}")
            if os.path.exists(destination):
                shutil.rmtree(destination)
                logging.debug(f"Cleanup successful: {destination}")
            else:
                logging.debug(f"Directory does not exist: {destination}")
    else:
        logging.error("Downloaded file not found, path incorrect, or not a valid ZIP file.")
    

def is_downloaded(gid, file_path=False):
    installfolder = config['SETTINGS'].get('install_location')
    path = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    game_name = path['title']
    destination = f"{installfolder}/Downloads/({gid}){game_name}/{os.path.basename(path['file_path'])}"
    if file_path:
        return destination
    return os.path.exists(destination)

def is_installed(gid):
    installfolder = config['SETTINGS'].get('install_location')
    game_data = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    game_name = game_data['title']
    destination = f"{installfolder}/Installations/({gid}){game_name}"
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
    foldername = fetch_game_info("NULL", "NULL", gid)  # Assuming fetch_game_info exists and returns a dictionary
    game_name = foldername['title']
    installfolder = config['SETTINGS'].get('install_location')
    destination = f"{installfolder}/Installations/({gid}){game_name}/"

    # List of executable names to ignore (with .exe appended)
    ignore_base_names = [
        "arc", "autorun", "bssndrpt", "crashpad_handler", "crashreportclient", 
        "crashreportserver", "dxdiag", "dxsetup", "dxwebsetup", "dxwebsetupinstaller", 
        "installationkit", "installationmanager", "installationscript", "installationwizard", 
        "installer", "installerassistant", "installersetup", "installerupdater", "installfile", 
        "installscript", "installwizard", "notification_helper", "oalinst", "patcher", 
        "patchinstaller", "patchmanager", "patchscript", "patchsetup", "patchupdater", 
        "python", "pythonw", "quicksfv", "quickuninstall", "sendrpt", "setup", 
        "setupassistant", "setupconfig", "setupfile", "setupinstaller", "setupkit", 
        "setupmanager", "setupscript", "setuputility", "setupwizard", "skidrow", 
        "smartsteaminstaller", "smartsteamloader_x32", "smartsteamloader_x64", 
        "smartsteamuninstaller", "ubisoftgamelauncherinstaller", "ue4prereqsetup_x64", 
        "unarc", "unins000", "unins001","unins002", "uninst", "uninstall", "uninstallagent", 
        "uninstallapplication", "uninstalldriver", "uninstaller", "uninstallerassistant", 
        "uninstallhandler", "uninstallhelper", "uninstallmanager", "uninstallprogram", 
        "uninstallscript", "uninstallservice", "uninstalltool", "uninstalltoolkit", 
        "uninstallupdater", "uninstallutility", "uninstallwizard", "unitycrashhandler", 
        "unitycrashhandler32", "unitycrashhandler64", "unrealcefsubprocess", "vc_redist.x64", 
        "vc_redist.x86", "vcredist_x64", "vcredist_x642", "vcredist_x643", "vcredist_x86", 
        "vcredist_x862", "vcredist_x863", "vcredist_x86_2008", "verify", "VC_redist.x86",
        "VC_redist.x64","DXSETUP","gfwlivesetup","GfWLPKSetter"
    ]
    ignore_list = {f"{name}.exe" for name in ignore_base_names}

    exes = []
    for root, dirs, files in os.walk(destination):
        for filename in files:
            if filename.endswith(".exe") and filename not in ignore_list:
                exes.append(os.path.join(root, filename))  # Include full path to the exe file
    return exes


def save_exe_selection(gid, exe):
    installfolder = config['SETTINGS'].get('install_location')
    path = fetch_game_info("NULL","NULL",gid) #User and pass not needed as it should already be in cache
    destination = f"{installfolder}/{gid}/.installed"
    with open(destination, 'w') as f:
        f.write(exe)

def get_exe_selection(gid):
    installfolder = config['SETTINGS'].get('install_location')
    game_data = fetch_game_info("NULL", "NULL", gid)  # Assuming fetch_game_info exists and returns a dictionary
    game_name = game_data['title']
    destination = f"{installfolder}/Installations/({gid}){game_name}/gamevault-exec"

    with open(destination, 'r') as f:
        for line in f:
            if 'Executable=' in line:
                return line.split('Executable=')[1].strip()
    
    raise ValueError("Executable not found in the configuration file")
    
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

def fetch_game_titles(username, password, online_status=True):
    gid = "game_titles"
    cached_data = load_cache(gid)
    
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    if cached_data:
        logging.debug("GV Client Online. Using cached game titles.")
    
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
            save_cache(gid, data)
            logging.debug("Cached game titles updated.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch game titles: {e}")
        return cached_data
    
def start_game(gid):
    executable = get_exe_selection(gid)
    print(executable)
    subprocess.run(executable)

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


def notification(title, message):
        notification = Notify()
        notification.title = title
        notification.message = message
        notification.icon = "bin/img/logo.png"
        notification.application_name = "GameVault-Snake"
        notification.send()



def save_image(image_data, type=None, gameid=None, username=None):
    cache_folder = os.path.join(settings_location, "cache")

    if type == "box_art":
        if gameid:
            cache_path = os.path.join(cache_folder, gameid, "box_art_image")
        else:
            return None
        
    elif type == "background_image":
        if gameid:
            cache_path = os.path.join(cache_folder, gameid, "BG_image")
        else:
            return None
    
    elif type == "user_profile_picture":
        if username:
            user_profile_folder = os.path.join(cache_folder, "profiles", username)
            os.makedirs(user_profile_folder, exist_ok=True)
            cache_path = os.path.join(user_profile_folder, "profile_picture")
        else:
            return None
    
    # Determine file extension based on image data's MIME type
    mime_type = "image/png"  # Assuming PNG for this example, you can adjust as needed
    extension = mimetypes.guess_extension(mime_type)
    if extension:
        cache_path += extension
    
    # Save the image to the specified cache_path
    with open(cache_path, "wb") as f:
        f.write(image_data)
    
    return cache_path

def get_user_info(username, password):
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {'accept': 'application/json', 'Authorization': f'Basic {encoded_credentials}'}
    response = requests.get(config["SETTINGS"]["url"] + "/api/users/me", headers=headers)
    response.raise_for_status()  # Raise an exception for non-200 status codes
    data = response.json()
    return data

def get_user_profile_picture(username, password):
    user_data = get_user_info(username, password)
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    if user_data:
        profile_picture_id = user_data.get('profile_picture', {}).get('id')
        if profile_picture_id:
            # Get profile picture
            headers = {'accept': 'application/json', 'Authorization': f'Basic {encoded_credentials}'}
            response = requests.get(config["SETTINGS"]["url"] + f"/api/images/{profile_picture_id}", headers=headers)
            response.raise_for_status()  # Raise an exception for non-200 status codes
            
            # Debugging: Print response content and headers
            # print("Response Content:", response.content)
            # print("Response Headers:", response.headers)

            # Check if response body is empty or not JSON
            if response.content:
                image_data = response.content
                # Save to cache and print image path
                image_path = save_image(image_data, type="user_profile_picture", username=username)
                print("Image Path:", image_path)
                return image_path
                
    return None  # Return None if there's an issue or no profile picture data

            




def load_and_place_image(self):
    user_profile_picture = get_user_profile_picture(username, keyring.get_password("GameVault-Snake", username))
    if user_profile_picture:
        
        # Open the image using PIL
        img = Image.open(user_profile_picture)
        # Convert the image to a PhotoImage object
        photo = customtkinter.CTkImage(light_image=img, dark_image=img, size=(25, 25))
        # Create a Label to hold the image
        image_label = customtkinter.CTkLabel(self, image=photo, text="")
        # Keep a reference to avoid garbage collection
        image_label.image = photo
        # Place the label in the upper right corner
        image_label.place(relx=1.0, rely=0.00, anchor="ne")
    else:
        img = Image.open("bin\img\pp_not_found.png")
        # Convert the image to a PhotoImage object
        photo = customtkinter.CTkImage(light_image=img, dark_image=img, size=(25, 25))
        # Create a Label to hold the image
        image_label = customtkinter.CTkLabel(self, image=photo, text="")
        # Keep a reference to avoid garbage collection
        image_label.image = photo
        # Place the label in the upper right corner
        image_label.place(relx=1.0, rely=0.00, anchor="ne")


def download_file(url, file_path,auth):
    dl = Pypdl(auth=auth)
    dl.start(url, file_path=file_path, segments=10, display=True, multisegment=True, block=False, retries=0, overwrite=False)

def fetch_game_info(username, password, gid):
    # Check if the response is already in the cache
    cached_data = load_cache(gid)
    if cached_data:
        logging.debug(f"Fetching from game info from cache...{gid}")
        return cached_data

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    url = f"{config['SETTINGS'].get('url')}/api/games/{gid}"
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

def download_game_files(username, password, gid):
    game_info = fetch_game_info(username, password, gid)
    if not game_info:
        logging.error("Failed to fetch game information.")
        return
    auth = aiohttp.BasicAuth(username, password)
    download_url = config["SETTINGS"].get("url") + f"/api/games/{gid}/download"
    game_name = game_info['title']
    install_location = config['SETTINGS'].get('install_location')
    download_path = os.path.join(install_location, f"Downloads/({gid}){game_name}.zip")

    # Create the download directory if it doesn't exist
    os.makedirs(os.path.dirname(download_path), exist_ok=True)

    # Download the file using pypdl
    download_file(download_url, download_path,auth)