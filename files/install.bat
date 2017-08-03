@echo off
echo Installing dependencies..
echo:
pip install -r %~dp0\requirements.txt

echo:
echo Installing display style..
start growl:display*https://raw.githubusercontent.com/senuido/stash-scanner/master/files/growl_display/compactdarkminimal.xml
echo:
pause