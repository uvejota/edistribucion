# edistribucion
Este es un proyecto apra poder consumir la API de e-distribución (Endesa distribución) y exponerla como un sensor dentro de Home Assistant. 
Actualmente está usando como backend el crawler de trocotronic. Por defecto está configurado para hacer update de nuestro contrador de edistribución cada 10 minutos. Esto es configurable en el configuration.yml no obstante no es recomendable dado que puede dar lugar a baneos por parte de la distribuidora. 

Como instalarlo:

Simplemente copia el contenido de este repositorio en la carpeta custom components y añade al configuration.yml el siguiente contenido:

``` yaml
  
sensor:
  - platform: edistribucion
    username: "username sin comillas"
    password: "password sin comillas"
    #scan_interval: 60 #This is in seconds. Mejor no usar para evitar baneos
```

 
# ¿Se pueden crear sensores con los atributos? 
Sí, se pueden crear de esta forma:

``` yaml
platform: template
sensors:
porcentaje_consumo_maximo:
friendly_name: "Porcentaje Consumo Máximo"
entity_id: sensor.eds_power_consumption
unit_of_measurement: '%'
value_template: "{{ state_attr('sensor.eds_power_consumption','Porcentaje actual')|replace(',','.')|replace('%','')|float }}"
```

TODO
=======
* Integrar el backend como dependencia pip
* Implementar la reconexion del ICP en cuanto el backend lo soporte. 
* Hacer que se integre en HUCS

Agradecimientos
=======
Agradecer a @trocotronic el trabajo de implementar el crwler para extraer los datos desde eds y a Miguel Macias por echar una mano animando a subir el código actualizado. 
