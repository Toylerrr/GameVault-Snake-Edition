import customtkinter
from CTkMenuBar import *
import configparser
import subprocess
from platformdirs import *
import os
import configparser
from .util import *


appname = 'GameVault-Snake Edition'
appauthor = 'Toylerrr'
settings_file_name = 'settings.ini'
settings_location = user_data_dir(appname, appauthor)
settings_file = os.path.join(settings_location, settings_file_name)

config = configparser.ConfigParser()
config.read(settings_file)
install_dir = config['SETTINGS'].get('install_location')


class MenuBar(CTkMenuBar):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.menu = CTkMenuBar(self)
        self.menu.grid(row=0, column=0, sticky="new",columnspan=2)
        button_1 = self.menu.add_cascade("View")
        button_2 = self.menu.add_cascade("Settings")
        button_3 = self.menu.add_cascade("AbouT")
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


        def change_appearance_mode_event(self, new_appearance_mode: str):
            customtkinter.set_appearance_mode(new_appearance_mode)
            config['SETTINGS']['apperance'] = new_appearance_mode
            with open(settings_file, 'w') as configfile:
                config.write(configfile)