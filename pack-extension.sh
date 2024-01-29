#!/bin/bash

icons=materialdesignicons-webfont

cp ./resources/fonts/$icons.*.ttf ./extension/chrome/$icons.ttf
cp ./resources/fonts/$icons.*.ttf ./extension/firefox/$icons.ttf
cd ./extension/
rm ./chrome.zip || true
rm ./firefox.zip || true
cd ./chrome/
zip -r ../chrome.zip *
cd ../firefox/
zip -r ../firefox.zip *
cd ..
rm ./chrome/$icons.ttf
rm ./firefox/$icons.ttf
