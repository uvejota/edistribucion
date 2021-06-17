# edistribucion
e-Distribución is an energy distribution company that covers most of South Spain area. If you live in this area, you probably are able to register into their website to get some information about your power demand, energy consumption, or even cycle billing (in terms of consumptions).

Although their application is great, this integration enables you to add a sensor to Home Assistant and getting updated automatically. However, it has some limitations yet, and no front-end support is being provided at the moment.

## How to install

1. Install HACS
2. Add this repo (https://github.com/uvejota/edistribucion) to the custom repositories in HACS
3. Install the integration. Please consider that alpha/beta versions are untested, and they might cause bans due to excesive polling.
4. Add this basic configuration at Home Assistant configuration files (e.g., `configuration.yml`)

``` yaml

sensor:
  - platform: edistribucion
    username: !secret eds_user # this key may exist in secrets.yaml!
    password: !secret eds_password # this key may exist in secrets.yaml!
```

At this point, you got an unique default sensor for the integration, namely `sensor.edistribucion`, linked to those credentials in the e-Distribución platform. This default sensor assumes the first CUPS that appears in the fetched list of CUPS, which frequently is the most recent contract, so this configuration may be valid for most users. If you need a more detailed configuration, please check the section below "What about customisation?".

## What about customisation?

This integration allows you to define some "extra" parameters in order to customise your installation. Check the following complete configuration, with annotations:

``` yaml
sensor:
  - platform: edistribucion
    username: !secret eds_user # this key may exist in secrets.yaml!
    password: !secret eds_password # this key may exist in secrets.yaml!
    cups: !secret eds_cups # optional, set your CUPS name. If you fail, it will select the first CUPS like by default
    short_interval: 3 # optional, number of minutes between meter updates (those that contain immediate lectures from your counter)
    long_interval: 60 # optional, number of minutes between cycle updates (those that contain immediate lectures from your counter)
    explode_sensors: # optional, to define extra sensors (separated from sensor.edistribucion) with the names and content specified below
      - cont # total counter energy in kWh
      - power_load # power load in %
      - power_limit # power limit in kWh
      - power # immediate power in kWh
      - energy_today # energy estimation for today in kWh (it requires to start a new day before reporting data)
      - energy_yesterday # energy estimation for yesterday in kWh (it may require a few hours to reflect the accumulated energy)
      - cycle_current # energy estimation for current billing cycle in kWh (it may require a few hours to reflect the accumulated energy)
      - cycle_last # energy estimation for the last billing cycle in kWh (it may require a few hours to reflect the accumulated energy)
      - power_peak # highest power peak in kW during the last 12 months
      - power_peak_mean # mean of monthly power peaks in kW during the last 12 months
      - power_peak_tile90 # percentile 90 of monthly power peaks in kW during the last 12 months
```

What if this configuration is not enough for you, and you have a great idea to save energy? 
>> Ask for it at https://github.com/uvejota/edistribucion/issues!

## Visualisation

Although we are not providing any custom front-end at the moment, you can use the following code to define some basic cards:

``` yaml
type: vertical-stack
title: Consumo eléctrico
cards:
  - type: sensor
    entity: sensor.edistribucion
    graph: line
    name: Potencia instantánea
    detail: 2
  - type: markdown
    content: >-
      **==================== Suministro ====================**
      
      **Contador:** {{ state_attr("sensor.edistribucion", "Contador") }} 
      
      **ICP:** {{ state_attr("sensor.edistribucion", "ICP") }}
      
      **==================== Consumo =====================**
      
      **Hoy:** {{ state_attr("sensor.edistribucion", "Energía hoy") }}
      
      **Ayer:** {{ state_attr("sensor.edistribucion", "Energía ayer") }} ({{ state_attr("sensor.edistribucion", "Detalle ayer") }})
      
      **Ciclo actual:** {{ state_attr("sensor.edistribucion", "Ciclo actual") }}
      
      **Ciclo anterior:** {{ state_attr("sensor.edistribucion", "Ciclo anterior") }}
      
      **==================== Potencia ======================**
      
      **Potencia:** {{ state_attr("sensor.edistribucion", "Potencia") }} 
      
      **Carga:** {{ state_attr("sensor.edistribucion", "Carga actual") }}
      
      **Potencia máx.:** {{ state_attr("sensor.edistribucion", "P. Pico") }} 
      
      **Potencia máx. (media):** {{ state_attr("sensor.edistribucion", "P. Pico (media)") }}
      
      **Potencia máx. (percentil 90):** {{  state_attr("sensor.edistribucion", "P. Pico (perc. 90)")  }}
      
      **==================================================**
    title: Informe
```

![image](https://github.com/uvejota/edistribucion/blob/master/docs/captures/20210615_capture.PNG)


## Credits

This repository is maintained by @uvejota and @jcortizronda for free, as a personal learning project. It was inspired by @jagalindo work (https://github.com/jagalindo/edistribucion), also maintaining some API-related code from @trocotronic repository (https://github.com/trocotronic/edistribucion).
