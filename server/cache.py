"""Cache TTL in memoria, con dimensione massima e scadenza."""
import threading, time


class TTLCache:
    def __init__(self, ttl=300.0, maxsize=512):
        self.ttl = ttl
        self.maxsize = maxsize
        self._dati = {}
        self._lock = threading.Lock()

    def get(self, chiave):
        with self._lock:
            voce = self._dati.get(chiave)
            if voce is None:
                return None
            scade, valore = voce
            if scade < time.time():
                self._dati.pop(chiave, None)
                return None
            return valore

    def set(self, chiave, valore):
        with self._lock:
            if len(self._dati) >= self.maxsize:
                scadute = [k for k, (s, _) in self._dati.items() if s < time.time()]
                for k in scadute:
                    self._dati.pop(k, None)
                while len(self._dati) >= self.maxsize:
                    self._dati.pop(next(iter(self._dati)))
            self._dati[chiave] = (time.time() + self.ttl, valore)

    def clear(self):
        with self._lock:
            self._dati.clear()
