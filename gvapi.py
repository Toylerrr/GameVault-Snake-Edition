import base64
import requests
import configparser
import os
import json


SETTINGS_FILE = 'settings.ini'
config = configparser.ConfigParser()
# Check if settings file exists, if not, create it with default values
if not os.path.exists(SETTINGS_FILE):
    # Create ConfigParser instance
    config = configparser.ConfigParser()

    # Set default values
    config['SETTINGS'] = {
        'username': '',
        'install_location': '',
        'url': ''
    }

    # Write the default configuration to the file
    with open(SETTINGS_FILE, 'w') as configfile:
        config.write(configfile)






config.read(SETTINGS_FILE)
URL = config['SETTINGS'].get('url')


def check_url_health(passedurl):
    try:
        response = requests.get(f'{passedurl}/api/health')
        if response.status_code == 200:
            json_data = response.json()
            if "status" in json_data and json_data["status"] == "HEALTHY":
                return True
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return False



CACHE_DIR = "cache"                             #This is where we will store the 
CACHE_FILE = f"{CACHE_DIR}/cached_games.json"   #This is all the games in one file

def fetch_game_titles(username, password):
    # Try to load cached data
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as file:
            cached_data = json.load(file)
        print("Using cached game titles.")
        return cached_data

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    url = f'{URL}/api/games'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Basic {encoded_credentials}'
    }
    params = {'sortBy': 'title:ASC'}

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        games = data['data']
        
        # Cache the fetched data
        with open(CACHE_FILE, "w") as file:
            json.dump(games, file)

        return games
    else:
        print("Failed to fetch game titles. Status code:", response.status_code)
        return None



# Define the directory for caching


# Create cache directory if it does not exist
os.makedirs(CACHE_DIR, exist_ok=True)

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
    if os.path.exists(CACHE_DIR):
        # Iterate over all files in the cache directory and remove them
        for filename in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Failed to remove {file_path}: {e}")
        print("Cache cleared successfully.")
    else:
        print("Cache directory does not exist. Nothing to clear.")


def fetch_game_info(username, password, gid):
    # Check if the response is already in the cache
    cached_data = load_cache(gid)
    if cached_data:
        print(f"Fetching from cache...{gid}")
        return cached_data

    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    url = f'{URL}/api/games/{gid}'
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
        print("Failed to fetch game info. Status code:", response.status_code)
        return None



# Example usage:
# domain = "http://"
# is_healthy = check_url_health(f'{domain}/api/health')
# print(f"The URL is healthy: {is_healthy}")

# Usage
# username = ''
# password = ''
# games = fetch_game_titles(username, password)
# for game in games:
#     print(f"Games: {game['title']}")

# Usage
# username = ''
# password = ''
# gid = 1
# game_infos = fetch_game_info(username, password, 1)
# if game_infos:
#     print(game_infos)  # Print the fetched game info ['title']
# else:
#     print("Failed to fetch game info.")
