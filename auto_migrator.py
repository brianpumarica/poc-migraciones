import time
import subprocess
import os
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

class ModelChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Check if the modified file is models.py
        if not event.is_directory and event.src_path.endswith('models.py'):
            print(f"Cambio detectado en {event.src_path}. Generando migración...")
            try:
                subprocess.run(["alembic", "revision", "--autogenerate", "-m", "auto-migracion"], check=True)
                print("Aplicando migración a la base de datos...")
                subprocess.run(["alembic", "upgrade", "head"], check=True)
                print("¡Migración completada con éxito!")
            except subprocess.CalledProcessError as e:
                print(f"¡Error en la migración! Revisa los logs. Código de salida: {e.returncode}")

if __name__ == "__main__":
    path = "./app" # Directorio a observar
    event_handler = ModelChangeHandler()
    observer = Observer()
    
    # Check if app directory exists before starting
    if not os.path.exists(path):
        print(f"El directorio {path} no existe. Saliendo.")
        exit(1)
        
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    print(f"Watchdog iniciado. Vigilando cambios en {path}/models.py...")
    print("Presiona Ctrl+C para detener.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo watchdog...")
        observer.stop()
    observer.join()
