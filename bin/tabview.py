import customtkinter
from platformdirs import *
import os
import configparser
from .util import *
import queue
from pySmartDL import SmartDL
import keyring
from bin.CTkPieChart import CTkPieChart
from notifypy import Notify
import notifypy
import functools
notifypy.Notify._selected_notification_system = functools.partial(notifypy.Notify._selected_notification_system, override_windows_version_detection=True)
from PIL import Image
import base64
import keyring
from bin.GUI.game_settings import GameSettings
from bin.CTkDataVisualizingWidgets import *
import pypdl


appname = 'GameVault-Snake Edition'
appauthor = 'Toylerrr'
settings_file_name = 'settings.ini'
settings_location = user_data_dir(appname, appauthor)
settings_file = os.path.join(settings_location, settings_file_name)

config = configparser.ConfigParser()
config.read(settings_file)
install_dir = config['SETTINGS'].get('install_location')

class MyTabView(customtkinter.CTkTabview):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)


        
        # create tabs
        self.add("Game")
        self.add("Downloads")
        self.tab("Game").rowconfigure(0, weight=1)
        self.tab("Game").columnconfigure(0, weight=1)
        self.tab("Downloads").rowconfigure(0, weight=1)
        self.tab("Downloads").columnconfigure(0, weight=1)

        # START GAME TAB
        self.prelabel = customtkinter.CTkLabel(self.tab("Game"), text="Select a Game to View", anchor="n", font=(None, 20))
        self.prelabel.grid(row=0, column=0, sticky="n", padx=10, pady=5)

        # everything after this shows once a game is selected
        self.game_window_frame = customtkinter.CTkFrame(self.tab("Game"), fg_color="transparent")
        # self.game_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.game_window_frame.columnconfigure(2, weight=1)

        self.game_image = customtkinter.CTkImage(size=(200, 300), light_image=Image.open("bin/img/not_found.jpg"))
        self.game_image_label = customtkinter.CTkLabel(self.game_window_frame, image=self.game_image, text="")
        self.game_image_label.grid(row=0, column=0, rowspan=2)

        self.game_name = customtkinter.CTkLabel(self.game_window_frame, text="NAME HERE", anchor="n", font=(None, 20))
        self.game_name.grid(row=0, column=1, columnspan=2, sticky="wn", padx=10, pady=5)
        self.game_config = customtkinter.CTkButton(self.game_window_frame, text="⚙️", anchor="center", fg_color="transparent", width=5)
        self.game_config.grid(row=0, column=2, sticky="ne")

        # CURRENT API DOESN'T SUPPORT SCREENSHOTS
        if config['SETTINGS'].get('debug') == 'True':
            self.screenshots = customtkinter.CTkScrollableFrame(self.game_window_frame, orientation="horizontal", fg_color="transparent")
            self.screenshots.grid(row=1, column=1, padx=10, pady=5, sticky="wens", columnspan=2)
            for i in range(1, 7):  # Loop from 1 to 6
                image_path = f"bin/img/ss_not_found.png"  # Assuming image filenames follow a pattern like ss_not_found_1.png, ss_not_found_2.png, etc.
                ss_image = customtkinter.CTkImage(light_image=Image.open(image_path), size=(334, 188))
                ss_label = customtkinter.CTkLabel(self.screenshots, image=ss_image, text="", anchor="s")
                ss_label.grid(row=0, column=i, padx=5, sticky="s")
            self.screenshots.rowconfigure(0, weight=1)

        self.activity_button = customtkinter.CTkButton(self.game_window_frame, text="")
        self.activity_button.grid(row=2, column=1, padx=10, pady=5)
        self.exe_selector = customtkinter.CTkComboBox(self.game_window_frame, state="readonly")
        self.exe_selector.set("Select an executable")
        self.exe_selector.grid(row=2, column=2, padx=5, pady=5, sticky="ew")
        self.description = customtkinter.CTkTextbox(self.game_window_frame, wrap="word")
        self.description.grid(row=3, column=1, columnspan=2, rowspan=4, sticky="we", padx=10, pady=5)
        self.activity_button.grid_info()
        self.release_year = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.release_year.grid(row=2, column=0, sticky="w")
        self.rating = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.rating.grid(row=3, column=0, sticky="w")
        self.version = customtkinter.CTkLabel(self.game_window_frame, justify="right", text="")
        self.version.grid(row=4, column=0, sticky="w")

        # END GAME TAB

        # START DOWNLOADS TAB
        self.download_window_frame = customtkinter.CTkFrame(self.tab("Downloads"), fg_color="transparent")
        self.download_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.download_window_frame.columnconfigure(0, weight=1)
        self.test_button = customtkinter.CTkButton(self.download_window_frame, text="Test DL", command=lambda: download_game_files(username,keyring.get_password("GameVault-Snake", username),"1"))
        self.test_button.grid(row=0, column=0, padx=10, pady=10)
        self.download_inner_frame = customtkinter.CTkFrame(self.download_window_frame)
        self.download_inner_frame.grid(row=1, column=0, padx=10, pady=10, sticky="NSWE", rowspan=6)
        self.fs_space_frame = customtkinter.CTkFrame(self.download_window_frame, fg_color="transparent")
        self.fs_space_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ews")
        self.pie_chart = CTkPieChart(self.fs_space_frame)
        self.pie_chart.grid(row=1, column=1, padx=10, pady=10)
        self.pie_chart.add("Free", get_disk_free(install_dir), color="green")
        self.pie_chart.add("Used", get_disk_usage(install_dir), color="blue")
        self.label_free = customtkinter.CTkLabel(self.fs_space_frame, text=f"Free: {int(get_disk_free(install_dir))}G\nUsed: {int(get_disk_usage(install_dir))}G\nTotal: {int(get_disk_total(install_dir))}G", anchor="w")
        self.label_free.grid(row=1, column=1, padx=10, pady=10)
