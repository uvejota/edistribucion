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
```

4. Representa la información obtenida con una tarjeta en Home Assistant, mientras trabajamos en su desarrollo puedes usar esta como modelo :-)

``` yaml

type: vertical-stack
cards:
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
  - type: sensor
    entity: sensor.eds_consumo_electrico
    graph: line
    name: Potencia instantánea
  - type: grid
    title: Resumen de consumos
    cards:
      - type: entity
        entity: sensor.eds_consumo_electrico
        name: Ayer
        attribute: Consumo total (ayer)
    columns: 2
    square: false
  - type: grid
    cards:
      - type: entity
        entity: sensor.eds_consumo_electrico
        attribute: Consumo total (7 días)
        name: 7 días
      - type: entity
        entity: sensor.eds_consumo_electrico
        attribute: Consumo total (30 días)
        name: 30 días
    columns: 2
    square: false
```

## Créditos

Repositorio mantenido por @uvejota y @jcortizronda como proyecto para el aprendizaje en tiempo libre y uso personal. 

Este repositorio parte de un fork del trabajo original realizado por @jagalindo (integración) y @trocotronic (API).
