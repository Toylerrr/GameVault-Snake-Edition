import customtkinter
from platformdirs import *
import os
import configparser
from .util import *
import keyring



appname = 'GameVault-Snake Edition'
appauthor = 'Toylerrr'
settings_file_name = 'settings.ini'
settings_location = user_data_dir(appname, appauthor)
settings_file = os.path.join(settings_location, settings_file_name)

config = configparser.ConfigParser()
config.read(settings_file)

username = config['SETTINGS'].get('username')
install_location = config['SETTINGS'].get('install_location')
url = config['SETTINGS'].get('url')





class Sidebar(customtkinter.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.logo_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.logo_frame.grid(row=0, column=0, sticky="nsew",)
        # self.logo_frame.grid_columnconfigure(0, weight=0)
        self.sidebar_frame = customtkinter.CTkScrollableFrame(self, corner_radius=0)
        self.sidebar_frame.grid(row=1, column=0, rowspan=4, sticky="nsew")
        # self.sidebar_frame.grid_columnconfigure(0, weight=1)

        self.logo_image = customtkinter.CTkImage(size=(200, 25), light_image=Image.open("bin/img/GV-dark.png"), dark_image=Image.open("bin/img/GV-light.png"))
        self.logo_label = customtkinter.CTkLabel(self.logo_frame, image= self.logo_image, text="")
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self.logo_frame.grid_columnconfigure(0, weight=0)

        
        # create sidebar frame with widgets

        # self.sorting_dropdown = customtkinter.CTkOptionMenu(self.sidebar_frame, values=["Name", "Year", "Rating"])
        # self.sorting_dropdown.grid(row=0, column=0, padx=0, pady=(20, 10), sticky="ew")

        games = fetch_game_titles(username, keyring.get_password("GameVault-Snake", username))
        # logging.debug(games)
        for game in games:
            fetch_game_info(username, keyring.get_password("GameVault-Snake", username), f"{game['id']}")
        sorted_games = sorted(games, key=lambda x: x[f'title'])
        for game in sorted_games:
            label = customtkinter.CTkButton(self.sidebar_frame, text=f"{game['title']}", corner_radius=0, fg_color="transparent", anchor="w")
            label.grid(row=sorted_games.index(game)+1, column=0, padx=0, pady=0, sticky="ew")