#!/bin/bash
set -euo pipefail

mkdir -p /etc/openwebrx/
mkdir -p /tmp/openwebrx/
if [[ ! -f /etc/openwebrx/config_webrx.py ]] ; then
  sed 's/temporary_directory = "\/tmp"/temporary_directory = "\/tmp\/openwebrx"/' < "/opt/openwebrx/config_webrx.py" > "/etc/openwebrx/config_webrx.py"
fi
if [[ ! -f /etc/openwebrx/bands.json ]] ; then
  cp bands.json /etc/openwebrx/
fi
if [[ ! -f /etc/openwebrx/bookmarks.json ]] ; then
  cp bookmarks.json /etc/openwebrx/
fi
if [[ ! -f /etc/openwebrx/users.json ]] ; then
  cp users.json /etc/openwebrx/
fi


_term() {
  echo "Caught signal!" 
  kill -TERM "$child" 2>/dev/null
}
    
trap _term SIGTERM SIGINT

python3 openwebrx.py $@ &

child=$! 
wait "$child"
    
