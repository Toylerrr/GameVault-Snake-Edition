# GameVault Snake Edition

If you like GameVault, consider donating to support the developers. They work hard and are far better at what they do than I am.

### Direct links to Phalcodes donations:
- GitHub Sponsors: [Phalcode](https://github.com/sponsors/Phalcode)
- Ko-fi: [Phalcode](https://ko-fi.com/phalcode)
- Liberapay: [Phalcode](https://liberapay.com/phalcode)
- GV+: [GV+](https://gamevau.lt/docs/gamevault-plus/introduction/)


![image](https://github.com/Toylerrr/GameVault-Snake-Edition/assets/4400902/a63a0cc6-fd5a-4e1a-bd59-6dc6c4cb6866)


## Overview
GameVault Snake Edition is my open-source Python launcher designed for the GameVault self-hosted server. It's my first significant coding project, still a work in progress. This will require major refactoring to get to a good "acceptable" point. 


## Functionality
- **Game Information Display:** Shows detailed information about selected games.
- **Settings Window:** Allows users to input and save their credentials securely.
- **Configuration Management:** Utilizes a settings file (`settings.ini`) to store and manage user preferences, including username, installation location, and URL.
- **Dynamic Content:** Retrieves game titles and information dynamically from the Gamevault server then caches it. 
- **Appearance Customization:** Supports customization of color themes and appearance modes. Create your own: https://github.com/Akascape/CTkThemeMaker
- **Download:** Current single download is working.


## Steamdeck
The client was made for the steamdeck funny enough it doesnt work on the steamdeck at this time. It can be used on other operating systems but I will not support it. I made this for me and my steamdeck.

## Security
This uses your OS keyring see here: https://github.com/jaraco/keyring
I did not and do not want to be responsible for your password or information that is why I used keyring to hand off all opsec to your OS. 

Remember don't run strange code from some guy on your devices ALWAYS look at the source code. - Some Guy

## EULA
I want to make it clear that I am not responsible for any issues, damages, or consequences that may arise from the use of this software. Users are responsible for their own actions and are encouraged to use the project responsibly and in accordance with applicable laws and regulations. By using Gamevault Snake Edition, users agree to waive any liability claims against me and understand that they are using the software at their own risk.

Gamevault Snake Edition is not part of the Phalcode software suite nor is it offically supported software. Use at your own risk.

## Support
Phalcode is not going to support the project or client via their discord. Do not ask for support in their discord for this client.

## Dependencies
tkinter
os
PIL import Image, ImageDraw
customtkinter
keyring
configparser
threading
subprocess
json
patoolib
pySmartDL
