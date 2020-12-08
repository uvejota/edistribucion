#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This example aims at testing the backend with no integration. Thanks a lot trocotronic for this backend
"""
Created on Wed May 20 11:51:36 2020

@author: trocotronic
"""
USER = ''
PASSWORD = ''

from backend.EdistribucionAPI import Edistribucion

edis = Edistribucion(USER,PASSWORD)
edis.login()
r = edis.get_cups()
cups = r['data']['lstCups'][0]['Id']
print('Cups: ',cups)
meter = edis.get_meter(cups)
print('Meter: ',meter)
