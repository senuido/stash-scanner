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
- `app.cfg`: contains league information and other preferences
  - `league` - league name (one of `Legacy, Hardcore Legacy, Standard, Hardcore Standard`)
  - `notification_duration` - minimum delay between notifications. if you get two notifications at once, this delay will allow you to respond convienently to both (since when a match is found a message is copied to the clipboard)
  - `request_delay`,`request_ahead_delay` - minimal delay between requests. Tweak these if you're getting throttled consistently.
- `filters.cfg`: contains item filters information, items will be matched according to these.

## Usage
- Configure preferences/filters
- Run Growl
- Run `AppGUI.py`

### Things to note
- You need to run PoE in windowed/windowed fullscreen mode for the notifications to show
- Python 3.x-3-5.x SHOULD work but only 3.5 was tested

### Why
Because there aren't any worthy public tools that do this at the API level.
Because trading in PoE sucks.