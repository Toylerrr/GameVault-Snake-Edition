from PIL import Image
import customtkinter
from bin.util import *
import keyring
import configparser
# from Settings_Wizard import InstallWizard
import subprocess
from platformdirs import *
import logging
import platform
from CTkMenuBar import *
from bin.tabview import MyTabView 
from bin.sidebar import Sidebar
from bin.menubar import MenuBar
import dateparser
from bin.GUI.game_settings import GameSettings
from bin.GUI.admin_settings import AdminSettings
from bin.GUI.gvse_settings import GVSESettings



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
        self.title(f"GameVaut: Snake Edition - Online: {online_status}")
        self.geometry("1200x600")
        self.minsize(1200,600)
        # Configure Grid
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(1, weight=1)


        #Stuff wasnt working so this code now lives here till fixed
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
        dropdown2.add_option(option="Admin Panel", command=lambda: AdminSettings(self))
        dropdown2.add_option(option="App Settings", command=lambda: GVSESettings(self))
        dropdown2.add_option(option="Settings Wizard", command=lambda: subprocess.run(["python", "Settings_Wizard.py"]))
        dropdown3 = CustomDropdownMenu(widget=button_3)
        dropdown3.add_option(option="Credits", command=lambda: print("open about here"))
        if config['SETTINGS'].get('debug') == 'True':
            button_4 = self.menu.add_cascade("Debug")
            dropdown4 = CustomDropdownMenu(widget=button_4)
            dropdown4.add_option(option="Clear Cache", command=lambda: clear_cache())
 

        def sidebar_callback(gid):
            #Select Game
            game_info=fetch_game_info(username, keyring.get_password("GameVault-Snake", username), gid)
            self.tab_view.prelabel.destroy()
            self.tab_view.game_window_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            self.tab_view.game_config.configure(command=lambda: open_game_settings(self, gid))

            self.tab_view.game_name.configure(text=game_info["title"])
            if game_info["description"]:
                self.tab_view.description.insert("0.0",game_info["description"])
            else:
                self.tab_view.description.delete("0.0", "end")
            if game_info["release_date"]:
                self.tab_view.release_year.configure(text=f"Release Year: {dateparser.parse(game_info["release_date"]).strftime("%Y")}")
            else:
                self.tab_view.release_year.configure(text="Release Year: Unknown")
            if game_info["metacritic_rating"]:
                self.tab_view.rating.configure(text=f"Rating: {game_info["metacritic_rating"]}")
            else:
                self.tab_view.rating.configure(text="Rating: Unknown")
            if game_info["version"]:
                self.tab_view.version.configure(text=f"Version: {game_info["version"]}")
            else:
                self.tab_view.version.configure(text="Version: Unknown")
            
            img_path = get_image(username, keyring.get_password("GameVault-Snake", username), gid, boxart=True)
            self.tab_view.game_image.configure(light_image=Image.open(img_path))

            if is_installed(gid):
                self.tab_view.activity_button.configure(text="Play", command=lambda: start_game(gid))
            elif is_downloaded(gid):
                print(f"This is downloaded: {is_downloaded(gid)}")
                print(is_downloaded(gid, file_path=True))
                self.tab_view.activity_button.configure(text="Install", command=lambda: unzip_game(gid))
            else:
                self.tab_view.activity_button.configure(text="Download", command=lambda: start_download(gid))
            
            if get_exes(gid):
                self.tab_view.exe_selector.configure(values=get_exes(gid))
                self.tab_view.exe_selector.set(get_exe_selection(gid))
            else:
                self.tab_view.exe_selector.configure(values=["Install to Play"])
                self.tab_view.exe_selector.set("Install to Play")            
            self.tab_view.set("Game")

        # self.menu = MenuBar(master=self)
        # self.menu.grid(row=0, column=0, sticky="nsew", columnspan=2)
        self.sidebar = Sidebar(master=self,fg_color="blue", callback=sidebar_callback)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.rowconfigure(1, weight=1)
        self.tab_view = MyTabView(master=self,anchor="s", fg_color="transparent")
        self.tab_view.grid(row=1, column=1, sticky="nsew")
        self.tab_view.rowconfigure(0, weight=1)

        def open_game_settings(self,gid):
            gamesettings = GameSettings(self,gameid=gid)





            
        #This is here so we can change the tabs    
        def start_download(gid):
            self.tab_view.download_game(username, keyring.get_password("GameVault-Snake", username), gid)
            self.tab_view.set("Downloads")
                # Load and place the floating image
        load_and_place_image(self)


    
    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)
        config['SETTINGS']['apperance'] = new_appearance_mode
        with open(settings_file, 'w') as configfile:
            config.write(configfile)
if __name__ == "__main__":
    app = App()
    app.mainloop()