# edistribucion
Integración para Home Assistant para la obtención de datos desde la web e-distribución. 

## Instalación

1. Añade este repositorio (https://github.com/uvejota/edistribucion) a los repositorios personalizados de HACS. 
2. Luego podrás instalar la integración.
3. Añade la siguiente configuración en Home Assistant (e.g., `configuration.yml`)

``` yaml

sensor:
  - platform: edistribucion
    username: 000000000A # username (e.g., dni)
    password: mySecurePassword # password
    scan_interval: inSeconds # optional (default = 600)
```

4. Representa la información obtenida con una tarjeta en Home Assistant, mientras trabajamos en su desarrollo puedes usar esta como modelo :-)

``` yaml
type: vertical-stack
title: Consumo eléctrico
cards:
  - type: sensor
    entity: sensor.eds_consumo_electrico
    graph: line
    name: Potencia instantánea
    detail: 2
  - type: grid
    cards:
      - type: entity
        entity: sensor.eds_consumo_electrico
        name: Hoy
        attribute: Consumo aproximado (hoy)
        unit: kWh
        icon: 'mdi:counter'
      - type: entity
        entity: sensor.eds_consumo_electrico
        name: Ayer
        attribute: Consumo (ayer)
        unit: kWh
        icon: 'mdi:counter'
      - type: entity
        entity: sensor.energia_facturada
        name: Facturado
      - type: entity
        entity: sensor.energia_facturada
        name: Factura anterior
        attribute: Consumo (últ. factura)
        unit: kWh
    columns: 2
    square: false
  - type: grid
    cards:
      - type: button
        tap_action:
          action: call-service
          service: homeassistant.update_entity
          service_data: {}
          target:
            entity_id: sensor.eds_consumo_electrico
        show_state: false
        icon: 'hass:update'
    square: true
    columns: 6
```

## Créditos

Repositorio mantenido por @uvejota y @jcortizronda como proyecto para el aprendizaje en tiempo libre y uso personal. 

Este repositorio parte de un fork del trabajo original realizado por @jagalindo (integración) y @trocotronic (API).
