import ttkbootstrap as tk
from tkinter import filedialog
import os
from PIL import Image
import customtkinter
from gvapi import *
import keyring
import configparser

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






class InstallWizard(customtkinter.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("400x400")
        self.resizable(False, False)  # Disallow resizing both horizontally and vertically
        self.title("GameVaut: Snake Edition - Setup")

        image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "img")
        # Create a frame to contain the widgets
        frame = customtkinter.CTkFrame(self,fg_color="transparent")
        frame.pack(padx=20, pady=20)

        # Image
        self.logo_image = customtkinter.CTkImage(light_image=Image.open(os.path.join(image_path, "GV-dark.png")), size=(200, 25), dark_image=Image.open(os.path.join(image_path, "GV-light.png")))
        self.logo_label = customtkinter.CTkLabel(frame, image=self.logo_image, text="")
        self.logo_label.grid(row=0, columnspan=2, pady=20)

        def validate_url():
            url = self.GV_URL.get()
            if url:
                is_valid = check_url_health(url)
                if is_valid:
                    self.GV_URL.configure(fg_color='green')  # Change text color to green for valid URL
                else:
                    self.GV_URL.configure(fg_color='red')    # Change text color to red for invalid URL
                return is_valid
            return False

        # GameVault URL Entry
        self.GV_URL = customtkinter.CTkEntry(frame, placeholder_text="GameVault URL IE: http:127.0.0.1:8080", validate="focusout", validatecommand=validate_url,width=350)
        self.GV_URL.grid(row=1, columnspan=2, pady=10, sticky="ew")

        # Username Entry
        self.username = customtkinter.CTkEntry(frame, placeholder_text="Username")
        self.username.grid(row=3, columnspan=2, pady=10)

        # Password Entry
        self.password = customtkinter.CTkEntry(frame, show="*", placeholder_text="Password")
        self.password.grid(row=4, columnspan=2, pady=10)

        # Install Location Entry
        self.install_location = customtkinter.CTkEntry(frame, placeholder_text="Install Location",width=300)
        self.install_location.grid(row=5, column=0, pady=10, sticky='ew',)

        # Select Folder Button
        self.select_location_button = customtkinter.CTkButton(frame, text='📁', command=self.select_install_location,width=30)
        self.select_location_button.grid(row=5, column=1, padx=(10, 0), pady=10,sticky='w')

        # Submit Button
        self.submit_il = customtkinter.CTkButton(frame, text='Submit', command=self.submit_credentials)
        self.submit_il.grid(row=6, columnspan=2, pady=10)

        self.close_label = customtkinter.CTkLabel(frame, text="")
        self.close_label.grid(row=7, columnspan=2, pady=10)
    
    def select_install_location(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.install_location.delete(0, 'end')
            self.install_location.insert(0, folder_selected)
            

    def submit_credentials(self):
        username = self.username.get()
        password = self.password.get()
        installoc = self.install_location.get()
        url = self.GV_URL.get()
        keyring.set_password("GameVault-Snake", username, password)
        config = configparser.ConfigParser()
        config.read('settings.ini')
        config.set('SETTINGS', 'username',username)
        config.set('SETTINGS', 'install_location',installoc)
        config.set('SETTINGS', 'url',url)
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)
        self.close_label.configure(text="Settings saved! Close and reopen to launch GameVault-Snake Edition.")



if __name__ == "__main__":
    InstallWizard().mainloop()
