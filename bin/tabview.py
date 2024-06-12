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

from bin.CTkDataVisualizingWidgets import *


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
        self.game_config = customtkinter.CTkButton(self.game_window_frame, text="⚙️", anchor="center", fg_color="transparent", width=5, command=lambda: print("OPEN GAME SETTINGS"))
        self.game_config.grid(row=0, column=2, sticky="ne")

        # CURRENT API DOESN'T SUPPORT SCREENSHOTS
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

        self.release_year = customtkinter.CTkLabel(self.game_window_frame, justify="right")
        self.release_year.grid(row=2, column=0, sticky="w")
        self.rating = customtkinter.CTkLabel(self.game_window_frame, justify="right")
        self.rating.grid(row=3, column=0, sticky="w")
        self.version = customtkinter.CTkLabel(self.game_window_frame, justify="right")
        self.version.grid(row=4, column=0, sticky="w")

        # END GAME TAB

        # START DOWNLOADS TAB
        self.download_window_frame = customtkinter.CTkFrame(self.tab("Downloads"), fg_color="transparent")
        self.download_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.download_window_frame.columnconfigure(0, weight=1)
        self.test_button = customtkinter.CTkButton(self.download_window_frame, text="Test DL", command=lambda: self.download_game(username, keyring.get_password("GameVault-Snake", username), 1))
        self.test_button.grid(row=0, column=0, padx=10, pady=10)

        self.download_inner_frame = customtkinter.CTkFrame(self.download_window_frame)
        self.download_inner_frame.grid(row=1, column=0, padx=10, pady=10, sticky="NSWE", rowspan=6)

        self.DL_Block1_label = customtkinter.CTkLabel(self.download_inner_frame, text="Currently Downloading: Long Name of a Game Here", anchor="w")
        self.DL_Block1_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block1_progressbar.set(0.0)
        self.DL_Block1_Pause_button = customtkinter.CTkButton(self.download_inner_frame, text="⏯️", width=5)
        self.DL_Block1_Stop_button = customtkinter.CTkButton(self.download_inner_frame, text="⏹️", width=5)

        self.fs_space_frame = customtkinter.CTkFrame(self.download_window_frame, fg_color="transparent")
        self.fs_space_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ews")
        self.pie_chart = CTkPieChart(self.fs_space_frame)
        self.pie_chart.grid(row=1, column=1, padx=10, pady=10)
        self.pie_chart.add("Free", get_disk_free(install_dir), color="green")
        self.pie_chart.add("Used", get_disk_usage(install_dir), color="blue")
        self.label_free = customtkinter.CTkLabel(self.fs_space_frame, text=f"Free: {int(get_disk_free(install_dir))}G\nUsed: {int(get_disk_usage(install_dir))}G\nTotal: {int(get_disk_total(install_dir))}G", anchor="w")
        self.label_free.grid(row=1, column=1, padx=10, pady=10)







    def check_download_progress(self, downloader, game_name, gid):
        self.DL_Block1_label.configure(text=f"Currently Downloading: {game_name}")
        self.DL_Block1_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block1_progressbar.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.DL_Block1_Pause_button.grid(row=0, column=2, padx=5)
        self.DL_Block1_Stop_button.grid(row=0, column=3, padx=5)

        if downloader.isFinished():
            if downloader.isSuccessful():
                print("Downloaded successfully:", downloader.get_dest())
                # Create gamevault-metadata file
                installfolder = config['SETTINGS'].get('install_location')
                with open(f"{installfolder}/Downloads/({gid}){game_name}/gamevault-metadata", "w") as file:
                    pass
                notification = Notify()
                notification.title = "Download Complete!"
                notification.message = f"{game_name} has been downloaded successfully!"
                notification.icon = "bin/img/logo.png"
                notification.application_name = "GameVault-Snake"
                notification.send()
            else:
                # Notify user that the download stopped or failed
                errors = downloader.get_errors()
                print(errors)
                if not errors:
                    error_message = 'Download was manually stopped by the user.'
                else:
                    error_message = f"An error occurred: {errors}"

                notification = Notify()
                notification.title = "Download Stopped!"
                notification.message = f"{game_name} has stopped downloading: {error_message}"
                notification.icon = "bin/img/logo.png"
                notification.application_name = "GameVault-Snake"
                notification.send()
                print("Download stopped with errors:", errors)
            
            # Clean up UI elements
            self.DL_Block1_label.grid_forget()
            self.DL_Block1_Pause_button.grid_forget()
            self.DL_Block1_Stop_button.grid_forget()
            self.DL_Block1_progressbar.grid_forget()
        else:
            # Update progress bar and check again after 100ms
            current_progress = downloader.get_progress()
            self.DL_Block1_progressbar.set(current_progress)
            self.after(100, lambda: self.check_download_progress(downloader, game_name, gid))

    def download_game(self, username, password, gid, force_redownload=False):
        # Encode credentials
        encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        
        # Construct API URL
        api_url = f'{url}/api/games/{gid}/download'
        
        # Get install folder from configuration
        installfolder = config['SETTINGS'].get('install_location')
        
        # Fetch game information
        game_data = fetch_game_info("NULL", "NULL", gid)
        game_name = game_data['title']
        file_path = game_data["file_path"]
        file_name = os.path.basename(file_path)
        
        # Determine download destination path
        destination = os.path.join(installfolder, f"Downloads/({gid}){game_name}", file_name)
        
        # Check if the game already exists and force redownload is not requested
        if not force_redownload and os.path.exists(destination):
            print("Game already downloaded:", destination)
            return destination
        
        # Set up request headers
        request_args = {"headers": {"Authorization": f'Basic {encoded_credentials}'}}
        
        # Initialize and start the downloader
        downloader = SmartDL(api_url, destination, request_args=request_args)
        downloader.start(blocking=False)
        
        # Configure buttons for download control
        self.DL_Block1_Pause_button.configure(command=lambda: toggle_pause(downloader))
        self.DL_Block1_Stop_button.configure(command=lambda: stop_downloader(downloader))
        
        # Check download progress
        self.check_download_progress(downloader=downloader, game_name=game_name, gid=gid)
        
        # Send notification that download has started
        notification("Download Started", f"{game_name} has started downloading!")
