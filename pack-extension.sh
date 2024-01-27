#!/bin/bash

fontname=materialdesignicons-webfont.7.4.47.ttf

cp ./resources/fonts/$fontname ./extension/chrome/icons
cd ./extension/
rm ./chrome.zip || true
rm ./firefox.zip || true
cd ./chrome/
zip -r ../chrome.zip *
cd ../firefox/
zip -r ../firefox.zip *
cd ..
rm ./chrome/icons/$fontname
