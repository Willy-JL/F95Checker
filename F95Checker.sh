#!/bin/bash
full_path=$(realpath $0)
dir_path=$(dirname $full_path)
python3 $dir_path/F95Checker.py
