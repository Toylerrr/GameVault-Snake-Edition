import tkinter as tk
from tkinter import filedialog
import os
from PIL import Image, ImageDraw
import customtkinter
from gvapi import *
import keyring
import configparser
from Settings_Wizard import InstallWizard
import threading
import subprocess


# Set appearance mode and default color theme
customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"
SETTINGS_FILE = 'settings.ini'

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
        #START DOWNLOADER
        def download_game(username, password, gid, force_redownload=False):
            encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            url = f'{URL}/api/games/{gid}/download'
            installfolder = config['SETTINGS'].get('install_location')
            path = fetch_game_info(username, password, gid)
            destination = f"{installfolder}/{gid}/download/{os.path.basename(path['file_path'])}"
            
            # Check if the file already exists and force_redownload is False
            if not force_redownload and os.path.exists(destination):
                print("Game already downloaded:", destination)
                return destination
            
            request_args = {"headers": {"Authorization": f'Basic {encoded_credentials}'}}
            downloader = SmartDL(url, destination, request_args=request_args)
            # threading.Thread(target=downloader.start).start()
            downloader.start(blocking=False)  # Starts the downloading process
            show_download_progress(path['title'])
            def update_progress():
                if downloader.get_status() == "downloading":
                    progress = downloader.get_progress()
                    speed = downloader.get_speed(human=True)
                    self.download_progress.set(progress)
                    # speed_label.configure(text=f"Speed: {speed}")
                    self.after(100, update_progress)
                elif downloader.get_status() == "finished":
                    self.download_progress.set['value'] = 1
                    
                    # speed_label.configure(text="Download completed.")
            update_progress()

        #END DOWNLOADER


        def async_download_game(username, password, game_id):
            t = threading.Thread(target=download_game, args=(username, password, game_id))
            t.start()
        

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
        m3.add_command(label="About",command=self.open_about)
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
        def selected_game(game_id):
            app.exe_selector.grid_forget()
            app.title_label.grid_forget()
            app.year_label.grid_forget()
            app.version_label.grid_forget()
            app.description_label.grid_forget()
            app.boxart_label.grid_forget()
            app.bg_label.place_forget()
            app.action_button.grid_forget()
            self.progressbar_1.place(relx=0.5, rely=0.5, anchor="center")
            self.progressbar_1.start()
            thread_get_game_info = threading.Thread(target=get_game_info, args=(game_id,))
            thread_get_game_info.start()
            # thread_get_boxart = threading.Thread(target=get_image, args=(username, keyring.get_password("GameVault-Snake", username),game_id,))
            # thread_get_boxart.start()
            # thread_add_gradient = threading.Thread(target=add_gradient, args=(username, keyring.get_password("GameVault-Snake", username),game_id,))
            # thread_add_gradient.start()


        def get_game_info(game_id):
            # Fetch game info
            game_infos = fetch_game_info(username, keyring.get_password("GameVault-Snake", username), game_id)
            if game_infos:
                # Update the labels with game information
                
                title = game_infos.get('title', 'N/A')
                release_date = game_infos.get('release_date', 'N/A')
                version = game_infos.get('version', 'N/A')
                description = game_infos.get('description', 'N/A')
                
                # Update the labels in the main frame
                boxartimg = customtkinter.CTkImage(light_image=Image.open(get_image(username, keyring.get_password("GameVault-Snake", username), game_id, boxart=True)),size=(133, 200))
                app.boxart_label.configure(image=boxartimg)
                bgimage = customtkinter.CTkImage(light_image=Image.open(add_gradient(username, keyring.get_password("GameVault-Snake", username), game_id)),size=(1920, 1080))
                # app.bg_label.configure(image=bgimage)
                self.begin_label.pack_forget()
                app.title_label.configure(text=title)
                app.year_label.configure(text=f"GAME RELEASE: {release_date}")
                app.version_label.configure(text=f"GAME Version: {version}")
                self.description_label.configure(state="normal")
                app.description_label.insert("0.0",text=description)
                def rungame():
                    exe = self.exe_selector.get()
                    save_exe_selection(game_id, exe)
                    subprocess.run(self.exe_selector.get(), shell=True)

                if is_installed(game_id) == True:
                    self.exe_selector.configure(values=get_exes_paths(game_id))
                    self.exe_selector.grid(row=2, column=0, pady=(20, 10), sticky="nsew")
                    if get_exe_selection(game_id) == None:
                        self.exe_selector.set("Select an executable")
                    else:
                        self.exe_selector.set(get_exe_selection(game_id))
                    self.action_button.configure(text= "Play",command=lambda: rungame())
                    self.action_button.grid(row=3, column=0, pady=(20, 10), sticky="nsew")
                elif is_downloaded(game_id) == True:
                    self.action_button.configure(text="Install",command=lambda: install_game(game_id))
                    self.action_button.grid(row=2, column=0, pady=(20, 10), sticky="nsew")
                else:
                    self.action_button.configure(text="Download",command=lambda: async_download_game(username, keyring.get_password("GameVault-Snake", username), game_id))
                    self.action_button.grid(row=2, column=0, pady=(20, 10), sticky="nsew")

                self.boxart_label.grid(row=1, column=0, pady=(20, 10), sticky="nsew")
                self.title_label.grid(row=0, column=1, pady=(20, 10), sticky="nsew",)
                self.year_label.grid(row=2, column=1, pady=(20, 10), sticky="nsew")
                self.version_label.grid(row=3, column=1, pady=(20, 10), sticky="nsew")
                # self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)  # Cover the entire frame
                
                self.description_label.grid(row=4, column=0, columnspan=2, pady=(20, 10), sticky="nsew")
                self.description_label.configure(state="disabled")
                self.progressbar_1.place_forget()
                


            else:
                print("Failed to fetch game info.")



        games = fetch_game_titles(username, keyring.get_password("GameVault-Snake", username))
        for game in games:
            fetch_game_info(username, keyring.get_password("GameVault-Snake", username), f"{game['id']}")
            #ADD LOADING SCREEN AND DONT USE MULTITHREADING ON STARTUP
            thread_add_gradient = threading.Thread(target=add_gradient, args=(username, keyring.get_password("GameVault-Snake", username), f"{game['id']}"))
            # thread_add_gradient.start()
        sorted_games = sorted(games, key=lambda x: x['title'])
        for game in sorted_games:
            label = customtkinter.CTkButton(self.sidebar_frame, text=f"{game['title']}", corner_radius=0, fg_color="transparent", anchor="w", command=lambda game_id=game['id']: selected_game(game_id),text_color=('black','white'))
            label.grid(row=sorted_games.index(game), column=0, padx=0, pady=0, sticky="ew")

        #____________________START MAIN WINDOW____________________
        self.main_frame = customtkinter.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent",)
        self.main_frame.grid(row=0, column=1, rowspan=3, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        #Background
        self.bg_label = customtkinter.CTkLabel(self.main_frame, text="")
        self.bg_label.lower()  # Lower the background label to the bottom of the stacking order


        self.begin_label = customtkinter.CTkLabel(self.main_frame, text="Select a Game",)
        self.begin_label.pack()
        self.boxart_label = customtkinter.CTkLabel(self.main_frame, text="")
        self.exe_selector = customtkinter.CTkComboBox(self.main_frame, state="readonly")
        self.action_button=customtkinter.CTkButton(self.main_frame,text="")

        self.title_label = customtkinter.CTkLabel(self.main_frame, text="",anchor="w")
        self.year_label = customtkinter.CTkLabel(self.main_frame, text="",anchor="w")
        self.version_label = customtkinter.CTkLabel(self.main_frame, text="",anchor="w")
        self.description_label = customtkinter.CTkTextbox(self.main_frame, width=800, wrap="word")

        self.progressbar_1 = customtkinter.CTkProgressBar(self.main_frame)
        self.progressbar_1.place(relx=0.5, rely=0.5, anchor="center")
        self.progressbar_1.configure(mode="indeterminnate")
        self.progressbar_1.start()
        self.progressbar_1.lift()
        self.progressbar_1.place_forget()

        def show_download_progress(gamename):
            self.dl_frame = customtkinter.CTkFrame(self, corner_radius=0, fg_color="transparent",)
            self.dl_frame.grid(row=3, column=1, sticky="nsew")
            self.dl_frame.grid_rowconfigure(0, weight=1)
            self.dl_frame.grid_columnconfigure(0, weight=1)
            self.spacingfixer = customtkinter.CTkLabel(self.dl_frame, text=f"Currently Downloading: {gamename}")
            self.spacingfixer.grid(row=0, column=0)
            self.download_progress = customtkinter.CTkProgressBar(self.dl_frame)
            self.download_progress.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0,5))
        
            











    def open_about(self):
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = AboutWindow(self)
        else:
            self.toplevel_window.focus() 







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
        self.submit_up = customtkinter.CTkButton(self, text="Clear Cache" ,command=lambda: clear_cache())
        self.submit_up.pack(padx=20, pady=20)


class AboutWindow(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("400x300")
        self.Informaiton = customtkinter.CTkTextbox(self, width=400, height=300,wrap="word")
        self.Informaiton.pack()
        self.Informaiton.insert("0.0",text="Not Offical and Not for Sale, If you bought this product in this form you were scammed this is licenced under MIT.")
        self.Informaiton.configure(state="disabled")
        



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
