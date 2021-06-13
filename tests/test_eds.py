#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Testing tool for a custom adaptation of the trocotronic API

ONLYNEW = True

import sys
sys.path.append('..')
from api.EdsHelper import EdsHelper

try:
    USER = sys.argv[1]
    PASSWORD = sys.argv[2]
except:
    print('Error while setting USER and PASSWORD variables')

# Try to login
eHelper = EdsHelper(USER,PASSWORD)
eHelper.update()

print(eHelper)