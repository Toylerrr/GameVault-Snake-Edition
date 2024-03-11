# GameVault Snake Edition
 

## Overview
GameVault Snake Edition is my open-source Python launcher designed for the GameVault self-hosted server. It's my first significant coding project, still a work in progress. While not feature-complete, it offers basic game functions. I welcome feedback and contributions from users to enhance its usability and usefulness.


## Functionality
- **Game Information Display:** Shows detailed information about selected games.
- **Settings Window:** Allows users to input and save their credentials securely.
- **Configuration Management:** Utilizes a settings file (`settings.ini`) to store and manage user preferences, including username, installation location, and URL.
- **Dynamic Content:** Retrieves game titles and information dynamically from an external source.
- **Appearance Customization:** Supports customization of color themes and appearance modes.

## Things that dont work
- **Server Managment:** You still must have a windows computer to manage the server
- **Game Remapping:** This client cant remap games to RAWG ids
- **User Page:** This client doesnt have any user page with whats being played
- **Playtime counter:** It doesnt track playtime as I didnt want to figure out a way to have it track time

## Usage
The application requires essential user information like username, installation location, and URL. If these values are missing, it initiates an installation wizard to gather necessary details. Upon completion, users can interact with the application to view game titles, access settings, and install games.

## Steamdeck
The client was made for the steamdeck. It can be used on other operating systems but I will not support it. I made this for me and my steamdeck.

## Support

Phalcode is not going to support the project or client via their discord. Do not ask for support in their discord for this client.

## Dependencies
- `ttkbootstrap`: for styling the GUI components.
- `tkinter`: for building the graphical interface.
- `PIL`: for image processing.
- `customtkinter`: for customized GUI elements.
- `gvapi`: for accessing game-related data.
- `keyring`: for securely storing user credentials.
- `configparser`: for managing configuration files.

