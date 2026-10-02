#!/bin/bash
LABEL="com.manish.mayatoon"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "Stopped $LABEL"
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist" && echo "Removed the login service"
echo "Your stories, scenes, keys and movies are still in $(cd "$(dirname "$0")" && pwd)/data. Delete the folder yourself if you want them gone."
