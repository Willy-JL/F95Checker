#!/bin/bash

cd ./extension/
rm ./chrome.zip || true
rm ./firefox.zip || true
cd ./chrome/
zip -r ../chrome.zip *
cd ../firefox/
zip -r ../firefox.zip *
