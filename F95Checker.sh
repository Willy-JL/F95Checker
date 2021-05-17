#!/bin/bash
full_path=$(realpath $0)
dir_path=$(dirname $full_path)
cd $dir_path/
python3 F95Checker.py
