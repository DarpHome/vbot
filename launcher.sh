#!/bin/bash

i=0

while [ $i -lt 3 ]; do
  ./vbot
  if [ $? -ne 0 ]; then
    echo "Running bot failed, retrying in 3 seconds"
    sleep 3
    i=$(expr $i + 1)
  else
    i=0
  fi
done
echo "Failed"
sleep 2592000