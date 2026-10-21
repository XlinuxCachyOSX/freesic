"""Test della preparazione dell'ambiente (usata da start.sh/start.bat).

La logica di avvio e' condivisa da Linux, macOS e Windows: qui si verifica
che i percorsi, la scelta della porta e la chiusura della vecchia istanza
funzionino su tutte le piattaforme.
"""
import os
import socket
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strumenti import prepara


class TestPercorsoPython(unittest.TestCase):
    """Il percorso dell'interprete cambia da Windows a Linux/macOS."""

    def test_windows_usa_scripts(self):
        with mock.patch.object(prepara.os, "name", "nt"):
            path = prepara.percorso_python_venv(prepara.VENV)
        self.assertTrue(str(path).endswith(os.path.join("Scripts", "python.exe")))

    def test_posix_usa_bin(self):
        with mock.patch.object(prepara.os, "name", "posix"):
            path = prepara.percorso_python_venv(prepara.VENV)
        self.assertTrue(str(path).endswith(os.path.join("bin", "python")))


class TestSceltaPorta(unittest.TestCase):

    def test_porte_libere_in_sequenza(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            occupata = s.getsockname()[1]
            # con la porta occupata si deve passare alla successiva
            scelta = prepara.scegli_porta(occupata, "127.0.0.1")
        self.assertGreater(scelta, occupata)
        self.assertLess(scelta, occupata + prepara.TENTATIVI_PORTA)

    def test_nessuna_porta_disponibile(self):
        # se tutte le porte sono occupate si torna alla porta iniziale
        with mock.patch.object(prepara, "porta_libera", return_value=False):
            self.assertEqual(prepara.scegli_porta(8000, "127.0.0.1"), 8000)


class TestIstanzaPrecedente(unittest.TestCase):

    def test_file_pid_inesistente(self):
        with mock.patch.object(prepara, "PID_FILE", self._file("/tmp/freesic-test-pid")):
            self.assertIsNone(prepara.chiudi_istanza_precedente())

    def test_pid_non_valido(self):
        path = self._file("/tmp/freesic-test-pid")
        with open(path, "w", encoding="utf-8") as f:
            f.write("non-e-un-pid")
        with mock.patch.object(prepara, "PID_FILE", path):
            prepara.chiudi_istanza_precedente()
        self.assertFalse(path.exists())

    def test_pid_morto_rimosso(self):
        path = self._file("/tmp/freesic-test-pid")
        with open(path, "w", encoding="utf-8") as f:
            f.write("999999")
        with mock.patch.object(prepara, "PID_FILE", path), \
                mock.patch.object(prepara, "processo_vivo", return_value=False):
            prepara.chiudi_istanza_precedente()
        self.assertFalse(path.exists())

    @staticmethod
    def _file(nome):
        from pathlib import Path
        return Path(nome)


if __name__ == "__main__":
    unittest.main()
