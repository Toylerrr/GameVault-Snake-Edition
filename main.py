import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageTk
import customtkinter
from bin.util import *
import keyring
import configparser
# from Settings_Wizard import InstallWizard
import threading
import subprocess
from platformdirs import *
import logging
import platform
from CTkMenuBar import *
from bin.tabview import MyTabView
from bin.sidebar import Sidebar
from bin.menubar import MenuBar




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
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

# Get values from config
username = config['SETTINGS'].get('username')
install_location = config['SETTINGS'].get('install_location')
url = config['SETTINGS'].get('url')




# Set appearance mode and default color theme
customtkinter.set_appearance_mode(config['SETTINGS'].get('apperance'))  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme(config['SETTINGS'].get('theme'))  # Themes: "blue" (standard), "green", "dark-blue"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        logging.debug(username)
        logging.debug(install_location)
        logging.debug(url)
        os_type = platform.system()
        logging.debug(os_type)
        # configure window
        self.title("GameVaut: Snake Edition")
        self.geometry("1200x600")
        # Configure Grid
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.menu = CTkMenuBar(self)
        self.menu.grid(row=0, column=0, sticky="new",columnspan=2)
        button_1 = self.menu.add_cascade("View")
        button_2 = self.menu.add_cascade("Settings")
        button_3 = self.menu.add_cascade("About")
        dropdown1 = CustomDropdownMenu(widget=button_1)
        dropdown1.add_option(option="Light theme", command=lambda: self.change_appearance_mode_event("Light"))
        dropdown1.add_option(option="Dark theme", command=lambda: self.change_appearance_mode_event("Dark"))
        dropdown1.add_option(option="System theme", command=lambda: self.change_appearance_mode_event("System"))
        dropdown2 = CustomDropdownMenu(widget=button_2)
        dropdown2.add_option(option="Admin Panel", command=lambda: print("open adminpanel here"))
        dropdown2.add_option(option="App Settings", command=lambda: print("open settings here"))
        dropdown2.add_option(option="Settings Wizard", command=lambda: subprocess.run(["python", "Settings_Wizard.py"]))
        dropdown3 = CustomDropdownMenu(widget=button_3)
        dropdown3.add_option(option="Credits", command=lambda: print("open about here"))



        # self.menu = MenuBar(master=self)
        # self.menu.grid(row=0, column=0, sticky="nsew", columnspan=2)
        self.sidebar = Sidebar(master=self,fg_color="blue")
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.rowconfigure(1, weight=1)
        self.tab_view = MyTabView(master=self,anchor="s", fg_color="transparent")
        self.tab_view.grid(row=1, column=1, sticky="nsew")
        self.tab_view.rowconfigure(0, weight=1)


    
    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)
        config['SETTINGS']['apperance'] = new_appearance_mode
        with open(settings_file, 'w') as configfile:
            config.write(configfile)
if __name__ == "__main__":
    app = App()
    app.mainloop()