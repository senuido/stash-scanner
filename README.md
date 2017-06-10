# Stash Scanner

## What it does
- Connects to PoE stash API and consumes stash information
- Parses items and attempts to find a match according to the configured filters
- When a match is found, a notification message is shown, a sound is played and a message is copied to the clipboard

## Installation
- Install [Python](https://www.python.org/ftp/python/3.5.2/python-3.5.2.exe)
- Install [Growl for Windows](http://www.growlforwindows.com/gfw/d.ashx?f=GrowlInstaller.exe), required for notifications
- Download stash scanner from the [releases page](../../releases) and extract it to a folder
- Run install.bat (run as administrator). This will install required dependencies & display style for growl
- Open Growl and set CompactDarkMinimal as default under display styles

## Configuration
Under `cfg` directory:
- `app.ini`: contains league information and other preferences
- `filters.json`: contains item filters information, items will be matched according to these.
- `filters.config.json`: contains mostly configuration for generated filters. price threshold, price overrides and such
- 'currency.json': contains currency information. currency names, rates, rates overrides, etc.

see configuration guide under `doc` directory.

## Usage
- Configure preferences/filters
- Run Growl
- Run `AppGUI.py`

### Things to note
- You need to run PoE in windowed/windowed fullscreen mode for the notifications to show
- Only Python 3.5 was tested, might be incompatible with previous version (don't even try 2.x)

### Why
Because there aren't any worthy public tools that do this at the API level.