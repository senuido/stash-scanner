# Stash Scanner

## What it does
- Retrieves item prices and currency rates from poe.ninja's API regularly
- Automatically generates filters according to retrieved item prices
- Allows you to configure your own item filters in a fashion similiar to poe.trade
- Connects to PoE stash API and consumes item information
- Parses items and attempts to find a match according to the configured filters
- When a match is found, a notification message is shown and a whisper message is copied to the clipboard

## What is it good for
- Snipe items you're interested in without having 20 tabs open on your browser, taxing your computer
- Be independant from poe.trade. without it as the middleman, you can potentially get your results faster
- Filter items based on API prices, less grunt work
- Filter items with custom mods, complementing any missing/unsuitable mods
- Easier filtering of crafting bases
- Easier management of your filters

## Installation
- Install [Growl for Windows](http://www.growlforwindows.com/gfw/d.ashx?f=GrowlInstaller.exe), required for notifications
- Download the bundle and extract it to a folder
- Run install_display_style.bat to install the display style for growl
- Open Growl and set CompactDarkMinimal as the default under display styles

## Usage
- Run Growl (for notifications)
- Run `Stash Scanner.exe`
- Configure league/preferences/filters. for reference see configuration guide
- Hit start

### Things to note
- You need to run PoE in windowed/windowed fullscreen mode for the notifications to show
- Use Python 3.5.x if not using the bundle

### Installation (if running from sources)
- Install [Python](https://www.python.org/ftp/python/3.5.2/python-3.5.2.exe)
- Install [Growl for Windows](http://www.growlforwindows.com/gfw/d.ashx?f=GrowlInstaller.exe), required for notifications
- Download Stash Scanner from the [releases page](../../releases/latest) and extract it to a folder
- Run install.bat (run as administrator). This will install required dependencies & display style for growl
- Open Growl and set CompactDarkMinimal as default under display styles
