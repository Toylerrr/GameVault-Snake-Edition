# GameVault Snake Edition
 

## Overview
GameVault Snake Edition is my open-source Python launcher designed for the GameVault self-hosted server. It's my first significant coding project, still a work in progress. While not feature-complete, it offers basic game management and administrative functions. I welcome feedback and contributions from users to enhance its usability and usefulness.

## Features
- **Admin Panel:** Provides access to administrative functions.
- **App Settings:** Allows users to configure application settings.
- **View Options:** Offers three appearance modes: Light, Dark, and System.
- **Help Menu:** Provides assistance and information.

## Functionality
- **Game Information Display:** Shows detailed information about selected games.
- **Settings Window:** Allows users to input and save their credentials securely.
- **Configuration Management:** Utilizes a settings file (`settings.ini`) to store and manage user preferences, including username, installation location, and URL.
- **Dynamic Content:** Retrieves game titles and information dynamically from an external source.
- **Appearance Customization:** Supports customization of color themes and appearance modes.

## Components
- **Main Frame:** Displays game information and settings.
- **Sidebar Frame:** Lists available games for selection.
- **Logo Frame:** Displays the application logo.
- **Settings Window:** Provides a separate window for managing user credentials.

## Usage
The application requires essential user information like username, installation location, and URL. If these values are missing, it initiates an installation wizard to gather necessary details. Upon completion, users can interact with the application to view game titles, access settings, and perform administrative tasks.

## Dependencies
- `ttkbootstrap`: for styling the GUI components.
- `tkinter`: for building the graphical interface.
- `PIL`: for image processing.
- `customtkinter`: for customized GUI elements.
- `gvapi`: for accessing game-related data.
- `keyring`: for securely storing user credentials.
- `configparser`: for managing configuration files.

