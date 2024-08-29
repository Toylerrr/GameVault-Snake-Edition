import customtkinter
import os
import configparser
from platformdirs import *
import keyring

class AdminSettings(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("400x400")
        self.resizable(False, False)  # Disallow resizing both horizontally and vertically
        self.title("GameVaut: Snake Edition - Settings")
        self.attributes("-topmost",True)  #the code is changed here
        self.attributes("-topmost",False)  #the code is changed here
        appname = 'GameVault-Snake Edition'
        appauthor = 'Toylerrr'
        settings_file_name = 'settings.ini'
        settings_location = user_data_dir(appname, appauthor)
        settings_file = os.path.join(settings_location, settings_file_name)
        config = configparser.ConfigParser()
        config.read(settings_file)
        main_scrolling_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        main_scrolling_frame.pack(fill="both", expand=True, padx=10, pady=10)

        label = customtkinter.CTkLabel(main_scrolling_frame, text="Admin Settings")
        label.pack()
        warning = customtkinter.CTkLabel(main_scrolling_frame, text="Warning: Changing these settings will require a restart.")
        warning.pack()
        warning2 = customtkinter.CTkLabel(main_scrolling_frame, text="currently cant change these settings here")
        warning2.pack() 
        for item in config['SETTINGS']:
            label = customtkinter.CTkLabel(main_scrolling_frame, text=item)
            label.pack()
            entry = customtkinter.CTkEntry(main_scrolling_frame, placeholder_text=config['SETTINGS'][item])
            entry.pack()


        def save_settings(setting, value):
            config['SETTINGS'][setting] = value
            with open(settings_file, 'w') as configfile:
                config.write(configfile)



        # Ensure settings directory exists
        os.makedirs(settings_location, exist_ok=True)
