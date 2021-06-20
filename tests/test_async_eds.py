#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Testing tool for a custom adaptation of the trocotronic API

import sys
import time
from datetime import datetime, timedelta
sys.path.append('..')
from api.EdsHelper import EdsHelper
import asyncio

try:
    USER = sys.argv[1]
    PASSWORD = sys.argv[2]
except:
    print('Error while setting USER and PASSWORD variables')


# Try to login
eHelper = EdsHelper(USER, PASSWORD, short_interval=timedelta(seconds=1), long_interval=timedelta(seconds=5))
asyncio.get_event_loop().run_until_complete(eHelper.async_update())
print(eHelper)
time.sleep(30)
print(eHelper)

'''
time.sleep(2)
eHelper.update()
print(eHelper)
time.sleep(10)
eHelper.update()
print(eHelper)
'''