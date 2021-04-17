#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Testing tool for a custom adaptation of the trocotronic API

ONLYNEW = True

import sys
from datetime import datetime, timedelta
sys.path.append('..')
from api.EdistribucionAPI import Edistribucion

try:
    USER = sys.argv[1]
    PASSWORD = sys.argv[2]
except:
    print('Error while setting USER and PASSWORD variables')

# Try to login
edis = Edistribucion(USER,PASSWORD, True)
edis.login()

# Try to get CUPS
r = edis.get_list_cups()
cups = r[0]['CUPS_Id']
cont = r[0]['Id']
print('Cups: ',cups)
print('Cont: ',cont)

# Try old stuff
if not ONLYNEW:
    meter = edis.get_meter(cups)
    print('Meter: ',meter)

# Try new stuff
yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
sevendaysago = (datetime.today()-timedelta(days=7)).strftime("%Y-%m-%d")
onemonthago = (datetime.today()-timedelta(days=30)).strftime("%Y-%m-%d")

yesterday_curve=edis.get_day_curve(cont,yesterday)
#print('Yesterday curve: ', yesterday_curve)
print(yesterday)
print('Yesterday Total Power: ', yesterday_curve['data']['totalValue'])

lastweek_curve=edis.get_week_curve(cont,sevendaysago)
#print('Lastweek curve: ', lastweek_curve)
print(sevendaysago)
print('Last week Total Power: ', lastweek_curve['data']['totalValue'])

lastmonth_curve=edis.get_month_curve(cont,onemonthago)
#print('Lastmonth curve: ', lastmonth_curve)
print(onemonthago)
print('Last month Total Power: ', lastmonth_curve['data']['totalValue'])
