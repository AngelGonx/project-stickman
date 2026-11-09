# Project Stickman

Stickmen animados que viven sobre tu barra de tareas de Windows. Caminan, hacen decenas de acciones, juegan en grupo, usan los objetos que les pongas, se pelean, se llaman por celular y persiguen tu cursor.

![Elenco](docs/elenco.png)

## Cómo correrlo

Doble clic en **`Iniciar.bat`** (la primera vez instala PySide6 solo). O a mano:

```bash
pip install -r requirements.txt
python desk_stickmen.py
```

Al cerrar el programa se guardan los stickmen que estaban en pantalla, y la próxima vez que lo abras vuelven los mismos. Los objetos **no** se guardan: cada vez que abres el programa empiezan sin objetos.

## Menú de la bandeja (ícono junto al reloj)

- **Agregar stickman**: los originales o los de tu biblioteca.
- **Crear stickman personalizado…**: círculo cromático para el color del cuerpo, de los accesorios y de los ojos, brillo, nombre, 18 cosméticos combinables y dos tipos de cuerpo (normal o **cabeza grande hueca**). Hay un botón de 🎲 aleatorio.
- **Biblioteca de personajes**: tus personajes guardados. Desde aquí los pones en pantalla, los editas o los borras. También puedes **exportar un respaldo** a un archivo e **importarlo** después.
- **Objetos**: sofá, mesa de picnic, pelota, trampolín, fogata, tele, cama, pesas, barra de dominadas, caja, patineta, maceta, pizza, libro, guitarra y bocina. Aparecen donde está tu cursor y los puedes arrastrar (la pelota la puedes lanzar). Clic derecho sobre un objeto para quitarlo.
- **Juegos**: arranca un juego de grupo cuando quieras.
- Pausar, ocultar, salir.

## Clic derecho sobre un stickman

Órdenes rápidas, **Acciones** (todas), **Usar objeto**, **Jugar**, **Con otro…** (pelear, las traes, chocar los cinco, etc.), **Guardar en la biblioteca**, **Editar apariencia…**, **Duplicar** y **Quitar de la pantalla**.

Arrástralos con el mouse para lanzarlos; un clic los hace reaccionar.

## Lo que hacen solos

- **Más de 40 acciones solos**: mortales, rueda de carro, pararse de manos, breakdance, moonwalk, baile robot, lagartijas, meditar levitando, dormir, karate, dab, volar como superhéroe, ver el celular, caminar viendo el celular, tomarse una selfie y muchas más.
- **Con objetos**: se sientan en el sofá (a veces con el celular), comen en la mesa de picnic, brincan en el trampolín con mortales, se calientan o asan bombones en la fogata, ven la tele, duermen en la cama, levantan pesas, hacen dominadas, se sientan en la caja, andan en patineta, riegan la planta (y crece), comen pizza (se va acabando), leen, tocan la guitarra, bailan junto a la bocina y patean la pelota.
- **Juegos de grupo**: parkour en fila, saltar la cuerda (dos la mueven y los demás brincan), limbo con una vara que va bajando, béisbol (lanzador, bateador y jardineros), pasarse la pelota que tú les des, carreras, piedra papel o tijera, tira y afloja, salto de rana y conga.
- **Llamadas**: uno marca, al otro le suena el celular donde esté, contesta y platican.
- **Entre dos**: se saludan, chocan los cinco o los puños, se dan la mano, hacen reverencia, bailan juntos, juegan a las traes o se pelean (con combos, patadas voladoras, barridas, bloqueos y esquives).
- **Salen corriendo de la nada**, y de vez en cuando notan tu cursor y lo persiguen.

## Ajustes rápidos

En `stickmen/core.py`: `HEIGHT` (tamaño), velocidades, `ACTIVIDAD` (qué tan inquietos son), `SPRINT_CADA` (cada cuánto salen corriendo) y `ENCUENTRO` (qué tan seguido se saludan, juegan o pelean). En `stickmen/crew.py`: `JUEGO_CADA` (cada cuánto arman un juego de grupo).

## Dónde se guarda todo

En la carpeta `datos/` junto al programa:

- `sesion.json`: quiénes estaban en pantalla la última vez.
- `personajes.json`: tu biblioteca de personajes.

## Código

| Archivo | Qué tiene |
|---|---|
| `desk_stickmen.py` | Punto de entrada |
| `stickmen/core.py` | Ajustes, elenco original, pantallas, poses y esqueleto |
| `stickmen/actions.py` | Todas las acciones animadas |
| `stickmen/draw.py` | Dibujo, cosméticos y objetos en la mano |
| `stickmen/stickman.py` | El comportamiento de cada stickman |
| `stickmen/objects.py` | Los objetos que colocas |
| `stickmen/games.py` | Los juegos de grupo y las llamadas |
| `stickmen/creator.py` | El creador de personajes |
| `stickmen/storage.py` | Sesión, biblioteca y respaldos |
| `stickmen/crew.py` | El grupo, la bandeja y los menús |

---
Pancracio Studios
