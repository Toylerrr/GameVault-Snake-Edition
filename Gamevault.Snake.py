import ttkbootstrap as tk
from tkinter import filedialog
import os
from PIL import Image
import customtkinter
from gvapi import *
import keyring
import configparser
from Settings_Wizard import InstallWizard

# Set appearance mode and default color theme
customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"
SETTINGS_FILE = 'settings.ini'

# Check if settings file exists, if not, create it with default values
# if not os.path.exists(SETTINGS_FILE):
#     # Create ConfigParser instance
#     config = configparser.ConfigParser()

#     # Set default values
#     config['SETTINGS'] = {
#         'username': '',
#         'install_location': '',
#         'url': ''
#     }

#     # Write the default configuration to the file
#     with open(SETTINGS_FILE, 'w') as configfile:
#         config.write(configfile)


# Read configuration from file
config = configparser.ConfigParser()
config.read(SETTINGS_FILE)

# Get values from config
username = config['SETTINGS'].get('username')
install_location = config['SETTINGS'].get('install_location')
url = config['SETTINGS'].get('url')

        
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        #GET CONFIG
        config = configparser.ConfigParser()
        config.read('settings.ini')
        username = config['SETTINGS']['username']
    


        # configure window
        self.title("GameVaut: Snake Edition")
        self.geometry(f"{1100}x{580}")

        # configure grid layout (4x4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure((2, 3), weight=0)
        self.grid_rowconfigure((1, 2,), weight=1)

        # Create menu bar
        menu_bar = tk.Menu(self)
        
        # Settings menu
        m1 = tk.Menu(menu_bar, tearoff=0)
        m1.add_command(label="Admin Panel")
        m1.add_separator()
        m1.add_command(label="App Settings",command=self.open_settings)
        menu_bar.add_cascade(label="Settings",menu=m1)
        self.toplevel_window = None
        # View menu
        m2 = tk.Menu(menu_bar, tearoff=0)
        m2.add_command(label="Light theme", command=lambda: self.change_appearance_mode_event("Light"))
        m2.add_command(label="Dark theme", command=lambda: self.change_appearance_mode_event("Dark"))
        m2.add_command(label="System theme",command=lambda : self.change_appearance_mode_event("System"))
        menu_bar.add_cascade(label="View",menu=m2)

        # Help menu
        m3 = tk.Menu(menu_bar, tearoff=0)
        m3.add_command(label="help!")
        menu_bar.add_cascade(label="Help",menu=m3)

        self.config(menu=menu_bar)

        # Logo frame
        self.logo_frame = customtkinter.CTkFrame(self, corner_radius=0)
        self.logo_frame.grid(row=0, column=0, sticky="new",)
        self.logo_frame.grid_columnconfigure(0, weight=0)
        
        # Logo label
        image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "img")
        self.logo_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(image_path, "GV-dark.png")), size=(200, 25), dark_image=Image.open(os.path.join(image_path, "GV-light.png")))
        self.logo_label = customtkinter.CTkLabel(self.logo_frame,image=self.logo_image, text="")
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self.logo_frame.grid_columnconfigure(0, weight=1)

        # create sidebar frame with widgets
        self.sidebar_frame = customtkinter.CTkScrollableFrame(self, corner_radius=0)
        self.sidebar_frame.grid(row=1, column=0, rowspan=3, sticky="nsew")
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        # Encode username and password

        
        # def selected_game(game_id):
        #     # Fetch game info
        #     game_infos = fetch_game_info(username, keyring.get_password("GameVault-Snake", username), game_id)
            
        #     if game_infos:
        #         # Create a string to hold all information
        #         info_string = ""
        #         for key, value in game_infos.items():
        #             info_string += f"{key}: {value}\n"

        #         # Update the text of the label in the main frame
        #         self.hero_img_label.configure(text=info_string)
        #     else:
        #         print("Failed to fetch game info.")

        def selected_game(game_id):
            # Fetch game info
            game_infos = fetch_game_info(username, keyring.get_password("GameVault-Snake", username), game_id)
            
            if game_infos:
                # Update the labels with game information
                title = game_infos.get('title', 'N/A')
                release_date = game_infos.get('release_date', 'N/A')
                version = game_infos.get('version', 'N/A')

                # Update the labels in the main frame
                app.title_label.configure(text=f"GAME TITLE: {title}")
                app.year_label.configure(text=f"GAME RELEASE: {release_date}")
                app.version_label.configure(text=f"GAME Version: {version}")
            else:
                print("Failed to fetch game info.")



        games = fetch_game_titles(username, keyring.get_password("GameVault-Snake", username))
        for game in games:
            fetch_game_info(username, keyring.get_password("GameVault-Snake", username), f"{game['id']}")
        sorted_games = sorted(games, key=lambda x: x['title'])
        for game in sorted_games:
            # print(f"Games: {game['title']}")
            label = customtkinter.CTkButton(self.sidebar_frame, text=f"{game['title']}", corner_radius=0, fg_color="transparent", anchor="w", command=lambda game_id=game['id']: selected_game(game_id),text_color=('black','white'))
            label.grid(row=sorted_games.index(game), column=0, padx=0, pady=0, sticky="ew")

        #____________________START MAIN WINDOW____________________
        self.main_frame = customtkinter.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, rowspan=3, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.title_label = customtkinter.CTkLabel(self.main_frame, text="")
        self.title_label.grid(row=0, column=0, pady=(20, 10))
        self.year_label = customtkinter.CTkLabel(self.main_frame, text="")
        self.year_label.grid(row=1, column=0, pady=(20, 10))
        self.version_label = customtkinter.CTkLabel(self.main_frame, text="")
        self.version_label.grid(row=3, column=0, pady=(20, 10))



        # game_infos = fetch_game_info(username, keyring.get_password("GameVault-Snake", username), 1)
        # if game_infos:


            
        #     # Create a string to hold all information
        #     info_string = ""
        #     for key, value in game_infos.items():
        #         info_string += f"{key}: {value}\n"
            
        #     self.hero_img_label = customtkinter.CTkLabel(self.main_frame, text=info_string)
        #     self.hero_img_label.grid(row=0, column=0, pady=(20, 10))
        #     self.hero_img_label.grid_columnconfigure(0, weight=1)
        # else:
        #     print("Failed to fetch game info.")

    def open_settings(self):
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = SettingsWindow(self)
        else:
            self.toplevel_window.focus()  # if window exists focus it    

    # Function to change appearance mode
    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    # Function to change scaling
    def change_scaling_event(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace("%", "")) / 100
        customtkinter.set_widget_scaling(new_scaling_float)

class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("400x300")

        self.username = customtkinter.CTkEntry(self, placeholder_text="Username")
        self.username.pack(padx=20, pady=20)
        self.password = customtkinter.CTkEntry(self, show="*", placeholder_text="Password")
        self.password.pack(padx=20, pady=20)
        self.submit_up = customtkinter.CTkButton(self, command=self.submit_credentials)
        self.submit_up.pack(padx=20, pady=20)
        self.submit_up = customtkinter.CTkButton(self, text="Clear Cache" ,command=clear_cache())
        self.submit_up.pack(padx=20, pady=20)



    def submit_credentials(self):
        username = self.username.get()
        password = self.password.get()
        keyring.set_password("GameVault-Snake", username, password)
        config = configparser.ConfigParser()
        config.read('settings.ini')
        config.set('SETTINGS', 'username',username)
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)


# Check if all required values are empty or whitespace
if not (username.strip() and install_location.strip() and url.strip()):
    InstallWizard().mainloop()
else:
    if __name__ == "__main__":
        app = App()
        app.mainloop()
