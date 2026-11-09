# Project Stickman

Stickmen animados que viven sobre tu barra de tareas de Windows. Caminan, corren, se sientan, saltan, se saludan, se pelean entre ellos y de repente notan tu cursor y lo persiguen.

![Elenco](docs/elenco.png)

## Cómo correrlo

Doble clic en **`Iniciar.bat`** (la primera vez instala PySide6 solo). O a mano:

```bash
pip install -r requirements.txt
python desk_stickmen.py
```

Aparecen 6 stickmen que caen desde arriba y aterrizan sobre la barra de tareas. Se controlan desde el ícono en la bandeja del sistema (agregar, quitar, pausar, ocultar, salir).

## Interacción

- **Arrastrar** con el mouse: lo agarras de la cabeza y lo puedes lanzar.
- **Clic**: saluda o salta.
- **Clic derecho**: órdenes, el submenú **Acciones** con todas las acciones, y **Con otro…** para que pelee, juegue a las traes o conviva con alguien.

## Comportamiento automático

La mayor parte del tiempo andan tranquilos (caminan, se paran, se sientan) y de vez en cuando hacen algo:

- **Más de 40 acciones solos:** mortales hacia adelante y atrás, rueda de carro, pararse de manos, voltereta, breakdance, moonwalk, baile robot, paso disco, guitarra de aire, lagartijas, sentadillas, saltos de tijera, meditar levitando, dormir, karate, dab, volar como superhéroe, barrerse, tropezar, estornudar, reírse, pensar, abrirse de piernas y más.
- **Salen corriendo de la nada** a toda velocidad (con líneas de velocidad).
- **El cursor:** a veces lo notan (aparece un **!**), lo miran y lo persiguen; si está justo arriba, saltan para atraparlo.
- **Cuando dos se cruzan:** se saludan, chocan los cinco, chocan puños, se dan la mano, hacen reverencia, bailan juntos, juegan a las traes o se pelean.
- **Peleas:** jab, cruzado, combos, gancho que manda volando, patada, patada giratoria, patada voladora, barrida, agarrar y lanzar, embestida, cabezazo, empujón, codazo y provocar. El otro puede bloquear, esquivar, agacharse o esquivar con mortal; si lo tiran, cae al piso y se levanta (a veces de un salto). Al final el ganador celebra y el perdedor hace berrinche, o se dan la mano si quedaron parejos.

## Ajustes rápidos

Al inicio de `desk_stickmen.py`: `HEIGHT` (tamaño), velocidades, `ACTIVIDAD` (qué tan inquietos son), `SPRINT_CADA` (cada cuánto salen corriendo), `ENCUENTRO` (qué tan seguido se saludan, juegan o pelean) y `ROSTER` (colores y accesorios de cada personaje).

## Elenco

Personajes originales: Uva (bufanda), Chicle (moño), Ola (gorra), Tinta (audífonos), Marino (lentes) y Brote (margarita).

---
Pancracio Studios
