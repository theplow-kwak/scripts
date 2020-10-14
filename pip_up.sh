#!/bin/bash

pip install --upgrade pip
pip freeze | cut -d'=' -f1 | xargs pip install --upgrade
