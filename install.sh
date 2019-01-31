#!/usr/bin/env bash

if ! pip3 install -r requirements.txt --user; then
  echo "ERROR: pip3 failed, see above"
  exit 1
fi

#./write_profile.py
