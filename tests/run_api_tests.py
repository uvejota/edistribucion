#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Testing tool for a custom adaptation of the trocotronic API

ONLYNEW = True

import sys
import json, requests
from datetime import datetime, timedelta
sys.path.append('..')
from api.EdistribucionAPI import Edistribucion
from pvpcbill import create_bill

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

    thismonth = datetime.today().strftime("%m/%Y")
    ayearplusamonthago = (datetime.today()-timedelta(days=395)).strftime("%m/%Y")
    maximeter_histogram = edis.get_year_maximeter (cups, ayearplusamonthago, thismonth)
    print(maximeter_histogram)
    print(maximeter_histogram['data']['maxValue'])

cycles = edis.get_list_cycles(cont)
last_cycle = cycles['lstCycles'][0]
print(last_cycle['label'])
print(last_cycle['value'])
cycle_curve = edis.get_cycle_curve(cont, last_cycle['label'], last_cycle['value'])
print(cycle_curve['totalValue'])
new_cycle_starting_date = datetime.strptime(last_cycle['label'].split(' - ')[1], '%d/%m/%Y') + timedelta(days=1)
print(new_cycle_starting_date)
thismonth_curve=edis.get_custom_curve(cont,new_cycle_starting_date.strftime("%Y-%m-%d"), datetime.today().strftime("%Y-%m-%d"))
print('This month Total Power: ', thismonth_curve['data']['totalValue'])
#csv = edis.get_cycle_csv(json.dumps(cycle_curve))
#print(csv)
#req = requests.get(csv_url)
#url_content = req.content
#print(url_content)