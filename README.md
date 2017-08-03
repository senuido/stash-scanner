# Stash Scanner
Stash scanner is a lightweight item searching tool for Path of Exile that works at the stash API level.  
The project is open-source, written in Python, licensed under [GNU GPLv3](license).

<img src=https://github.com/senuido/stash-scanner/raw/master/files/images/stash_scanner.png width=300 height=150>
<img src=https://github.com/senuido/stash-scanner/raw/master/files/images/filter_editor.jpg width=300 height=150>

## Features
- Advanced searching capabilities, comparable to poe.trade
- Supports currency conversion based on rates from poe.ninja
- Automatically generates filters for valuable items based on prices from poe.ninja
- Allows for currency rates and prices customization to better suit your needs
- Allows you to configure your own item filters which can:
  - have their price be based on API prices
  - relate to other filters, allowing easier management
  - Use custom mods to complement missing mods or allow for more advanced searches
- Alerts when a match is found, a notification message is shown and a whisper message is copied to the clipboard
- Stores a minimal amount of information to prevent unnecessary notifications (it does not index items).
- Directly connects to the PoE stash API. without a middleman, you can get your results faster

## Installation
- Install [Growl for Windows](http://www.growlforwindows.com/gfw/d.ashx?f=GrowlInstaller.exe), required for notifications
- [Download the bundle](../../releases/latest) and extract it to a folder
- Run *install_display_style.bat* to install the display style for Growl
- Open Growl and set *CompactDarkMinimal* as the default under display styles

## Usage
- Run Growl (for notifications)
- Run `Stash Scanner.exe`
- Configure league/preferences/filters. for reference, see [configuration guide](/doc/configuration.md)
- Click start to start scanning  

Note: you must run PoE in windowed or windowed fullscreen mode for the notifications to show while in-game

## Support
This project is being developed in my free time.  
If this project is useful to you, please consider making a donation, even a small one!  

[![Donate](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=YQ7F5L7AS2A5Y)
