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
