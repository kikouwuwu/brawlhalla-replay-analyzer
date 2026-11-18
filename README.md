# Brawlhalla Replay Analyzer

Herramienta en Python que lee los archivos `.replay` que guarda Brawlhalla y te dice **qué estás haciendo mal**: qué ataques repites demasiado, cuánto esquivas, qué hacías antes de perder cada stock y qué conviene cambiar.

```
== kikou  [leyendas: 4]
   Acciones por minuto: 27
   Ataques: 26  |  Dodges: 1  |  Saltos: 1
   Ataques más usados:
     light_side       25    96%
     sig_down          1     4%
   Muertes:
     #1 a los 5.6s (stock de 5.6s) — últimos inputs: light_side, light_side, dodge_spot, sig_down, jump
   Qué mejorar:
     - El 96% de tus ataques es light_side. Eres predecible: un rival atento va a esperar ese ataque y castigarlo.
     - En 1 de 1 muertes esquivaste en el último segundo: es probable que te estén leyendo el dodge y castigando el cooldown.
```

## Instalación

Requiere Python 3.9+. El parser no tiene dependencias externas.

```bash
git clone https://github.com/kikouwuwu/brawlhalla-replay-analyzer.git
cd brawlhalla-replay-analyzer
pip install -e .
```

## Uso

```bash
bhanalyze ruta/a/partida.replay            # analiza un replay
bhanalyze --latest                         # el más reciente de ~/BrawlhallaReplays
bhanalyze --latest --player "TuNombre"     # solo tu jugador
bhanalyze partida.replay --json            # salida en JSON para seguir analizando
```

En Windows, Brawlhalla guarda los replays en `C:\Users\<usuario>\BrawlhallaReplays`. Hay que activar el guardado de replays en las opciones del juego.

También se puede usar como librería:

```python
from bhanalyzer import parse_file, analyze

replay = parse_file("partida.replay")
for stats in analyze(replay).values():
    print(stats.name, stats.attacks.most_common(3))
```

## Cómo funciona

1. **Descompresión y desofuscación**: el `.replay` es un stream zlib cuyos bytes están ofuscados con un XOR cíclico de 64 bytes. Los datos se leen bit a bit.
2. **Parseo**: header (modo y seed), configuración de la partida, jugadores y leyendas, resultados, momentos de cada KO y la lista de inputs de cada jugador con su timestamp.
3. **Análisis**: los inputs son cambios de estado de los botones. Cada botón recién presionado se convierte en una acción (`light_side`, `sig_down`, `dodge_spot`, `jump`…) usando la dirección que se mantenía en ese momento. Con eso se calculan frecuencias, acciones por minuto y el contexto de cada muerte.
4. **Insights**: reglas simples que detectan patrones comunes, como ser predecible, abusar del dodge, esquivar justo antes de morir o quedarse quieto bajo presión.

## Limitaciones

El replay **no guarda posiciones, daño ni golpes conectados**. El juego reconstruye la partida re-simulando los inputs. Por eso:

- No se distingue un ataque en el suelo de uno aéreo (`light_neutral` puede ser nlight o nair).
- No se sabe si un ataque conectó ni quién golpeó a quién.
- Los IDs de leyenda y mapa se muestran como número, porque todavía no están mapeados a nombres.
- El formato cambia con los parches del juego, así que un replay muy nuevo podría no leerse.

## Roadmap

- [ ] Mapear IDs de leyendas y mapas a nombres
- [ ] Comparar varias partidas para ver tendencias a lo largo del tiempo
- [ ] Dashboard con gráficos (Streamlit)
- [ ] Fase 2: grabar la reproducción del replay y extraer daño y posición con visión por computador

## Créditos

El formato del replay está basado en [BrawlhallaReplayLibrary](https://github.com/allhailcheese/BrawlhallaReplayLibrary) (MIT) y [brawlhalla-replay-reader](https://github.com/itselectroz/brawlhalla-replay-reader). Proyecto no afiliado a Blue Mammoth Games ni a Ubisoft.

## Licencia

MIT
