import customtkinter
import os
from bin.util import *

class GameSettings(customtkinter.CTkToplevel):
    def __init__(self, parent, gameid, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self.geometry("400x400")
        self.resizable(False, False)  # Disallow resizing both horizontally and vertically
        self.title("GameVaut: Snake Edition - Settings")
        # self.after(200, lambda: self.iconbitmap("bin\img\logo.png"))
        self.attributes("-topmost",True)  #the code is changed here
        self.attributes("-topmost",False)  #the code is changed here
        game_info = fetch_game_info(username, keyring.get_password("GameVault-Snake", username), gameid)

        title_label = customtkinter.CTkLabel(self, text=game_info['title'])
        title_label.pack(pady=5)
        gid_label = customtkinter.CTkLabel(self, text=f"Game ID is {gameid}")
        gid_label.pack(pady=5)

        image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "img")
