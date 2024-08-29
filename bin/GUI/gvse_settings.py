import customtkinter
import os

class GVSESettings(customtkinter.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        gameid = kwargs.get("gameid")
        
        self.geometry("400x400")
        self.resizable(False, False)  # Disallow resizing both horizontally and vertically
        self.title("GameVaut: Snake Edition - Settings")
        # self.after(200, lambda: self.iconbitmap("bin\img\logo.png"))
        self.attributes("-topmost",True)  #the code is changed here
        self.attributes("-topmost",False)  #the code is changed here

        label = customtkinter.CTkLabel(self, text=gameid)
        label.pack(padx=20, pady=20)

        image_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "img")