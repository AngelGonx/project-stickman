#!/usr/bin/env python3
"""
Desk Stickmen — stickmen animados que viven sobre tu barra de tareas.

Caminan, hacen decenas de acciones, juegan en grupo (parkour, cuerda, limbo,
béisbol...), usan los objetos que les pongas, pelean, se llaman por celular y
persiguen tu cursor. Todo se controla desde el ícono de la bandeja del sistema
y con clic derecho sobre cada stickman.

Requisitos:  pip install PySide6
Ejecutar:    python desk_stickmen.py   (o doble clic en Iniciar.bat)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stickmen.crew import main  # noqa: E402

if __name__ == "__main__":
    main()
