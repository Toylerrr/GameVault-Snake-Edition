import customtkinter
from platformdirs import *
import os
import configparser
from .util import *
import queue
from pySmartDL import SmartDL
import keyring

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


    #START GAME TAB
        self.prelabel = customtkinter.CTkLabel(self.tab("Game"), text="Select a Game to View",anchor="n",font=(None,20))
        self.prelabel.grid(row=0, column=0,sticky="n",padx=10, pady=5)

        #everything after this shows once a game is selected
        self.game_window_frame = customtkinter.CTkFrame(self.tab("Game"), fg_color="transparent")
        # self.game_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.game_window_frame.columnconfigure(2, weight=1)
        

        self.game_image = customtkinter.CTkImage(size=(200, 300), light_image=Image.open("bin/img/not_found.jpg"))
        self.game_image_label = customtkinter.CTkLabel(self.game_window_frame, image= self.game_image, text="")
        self.game_image_label.grid(row=0, column=0,rowspan=2)

        self.game_name=customtkinter.CTkLabel(self.game_window_frame, text="NAME HERE",anchor="n",font=(None,20))
        self.game_name.grid(row=0, column=1,sticky="wn",padx=10, pady=5)


        #CURRENT API DOSNT SUPPORT SCREENSHOTS
        # self.screenshots=customtkinter.CTkScrollableFrame(self.game_window_frame, orientation="horizontal",fg_color="transparent")
        # self.screenshots.grid(row=1, column=1,padx=10, pady=5, sticky="wens",columnspan=2)
        # for i in range(1, 7):  # Loop from 1 to 6
        #     image_path = f"bin/img/ss_not_found.png"  # Assuming image filenames follow a pattern like ss_not_found_1.png, ss_not_found_2.png, etc.
        #     ss_image = customtkinter.CTkImage(light_image=Image.open(image_path), size=(334, 188))
        #     ss_label = customtkinter.CTkLabel(self.screenshots, image=ss_image, text="",anchor="s")
        #     ss_label.grid(row=0, column=i, padx=5, sticky="s")
        # self.screenshots.rowconfigure(0, weight=1)


        self.activity_button = customtkinter.CTkButton(self.game_window_frame, text="Activity", command=lambda: start_download("https://ash-speed.hetzner.com/10GB.bin", "C:\\Users\\tyler\\Desktop\\test-dest"))        
        self.activity_button.grid(row=2, column=1,padx=10, pady=5)
        self.exe_selector = customtkinter.CTkComboBox(self.game_window_frame, state="readonly")
        self.exe_selector.set("Select an executable")
        self.exe_selector.grid(row=2, column=2, padx=5, pady=5, sticky="ew")

        self.description=customtkinter.CTkTextbox(self.game_window_frame,wrap="word")
        self.description.grid(row=3, column=1,columnspan=2, rowspan=4, sticky="we", padx=10, pady=5)
        self.activity_button.grid_info()


        self.release_year=customtkinter.CTkLabel(self.game_window_frame, text="Release Year: YEAR HERE",justify="right")
        self.release_year.grid(row=2, column=0,sticky="w")
        self.rating=customtkinter.CTkLabel(self.game_window_frame, text="Rating: RATING HERE",justify="right")
        self.rating.grid(row=3, column=0,sticky="w")
        self.version=customtkinter.CTkLabel(self.game_window_frame, text="Version: VERSION HERE",justify="right")
        self.version.grid(row=4, column=0, sticky="w")





    #END GAME TAB


    #START DOWNLOADS TAB
        self.download_window_frame = customtkinter.CTkFrame(self.tab("Downloads"), fg_color="transparent")
        self.download_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.download_window_frame.columnconfigure(0, weight=1)
        self.test_button = customtkinter.CTkButton(self.download_window_frame, text="Test DL", command=lambda: start_test("https://ash-speed.hetzner.com/10GB.bin", "C:\\Users\\tyler\\Desktop\\test-dest"))
        self.test_button.grid(row=0, column=0, padx=10, pady=10)

        self.download_inner_frame = customtkinter.CTkFrame(self.download_window_frame)
        self.download_inner_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        #5 blocks of progress bars

        self.DL_Block1_label = customtkinter.CTkLabel(self.download_inner_frame, text="Block 1")
        self.DL_Block1_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block1_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block1_progressbar.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.DL_Block2_label = customtkinter.CTkLabel(self.download_inner_frame, text="Block 2")
        self.DL_Block2_label.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block2_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block2_progressbar.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.DL_Block3_label = customtkinter.CTkLabel(self.download_inner_frame, text="Block 3")
        self.DL_Block3_label.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block3_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block3_progressbar.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.DL_Block4_label = customtkinter.CTkLabel(self.download_inner_frame, text="Block 4")
        self.DL_Block4_label.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block4_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block4_progressbar.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        self.DL_Block5_label = customtkinter.CTkLabel(self.download_inner_frame, text="Block 5")
        self.DL_Block5_label.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.DL_Block5_progressbar = customtkinter.CTkProgressBar(self.download_inner_frame, orientation="horizontal")
        self.DL_Block5_progressbar.grid(row=4, column=1, padx=10, pady=10, sticky="ew")


        self.fs_space_frame = customtkinter.CTkFrame(self.download_window_frame, fg_color="transparent")
        self.fs_space_frame.grid(row=1, column=2, padx=10, pady=10, sticky="ews")
