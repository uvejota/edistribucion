#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Testing tool for a custom adaptation of the trocotronic API

import sys
import time
from datetime import datetime, timedelta
sys.path.append('..')
from api.EdsHelper import EdsHelper

try:
    USER = sys.argv[1]
    PASSWORD = sys.argv[2]
except:
    print('Error while setting USER and PASSWORD variables')


# Try to login
eHelper = EdsHelper(USER, PASSWORD, short_interval=timedelta(seconds=1), long_interval=timedelta(seconds=5))
eHelper.update()
print(eHelper)
time.sleep(2)
eHelper.update()
print(eHelper)
time.sleep(10)
eHelper.update()
print(eHelper)