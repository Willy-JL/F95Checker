#!/bin/bash

cd ./extension/chrome/
google-chrome-stable --pack-extension=$PWD ; rm $PWD/../chrome.pem
cd ../firefox/
zip -r ../firefox.zip * ; mv ../firefox.zip ../firefox.xpi
