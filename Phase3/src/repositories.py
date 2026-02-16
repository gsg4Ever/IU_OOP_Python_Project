from __future__ import annotations

# -----------------------------------------------------------------------------
# Repository-Schicht (SQLite/Persistenz)
# -----------------------------------------------------------------------------
# In den Repositories steckt der komplette SQL-Zugriff (CRUD + ein paar Abfragen für KPIs).
# Die UI sieht davon nichts, sie spricht nur mit dem Service.
# -----------------------------------------------------------------------------


from datetime import date
from typing import Any, Optional

from Phase3.src.db import DatabaseProtocol
from Phase3.src.models import Modul, ModulBelegung, Student, Studiengang


def _iso(d: Optional[date]) -> Optional[str]:
    """
    Konvertiert ein Datum in das ISO-Format für die Datenbank.
    
    Kurz:
        Repositories speichern Datumswerte als TEXT im Format `YYYY-MM-DD`. Diese Hilfsfunktion
        übernimmt die Serialisierung und behandelt `None` sauber.
    
    Parameter:
        d (date | None): Datum oder `None`.
    
    Gibt zurück:
        str | None: ISO-String oder `None`.
    """

    return d.isoformat() if d else None


class StudentRepository:
    """
    Repository für `Student` (Persistenzzugriff).
    
    Kurz:
        Kapselt SQL-Zugriffe auf die Tabelle `student` und stellt eine einfache Upsert-Operation bereit.
    
    Hinweis:
        Im Prototypen wird `matrikelnummer` als natürlicher Schlüssel verwendet.
        `upsert()` nutzt `ON CONFLICT` und liefert die `student_id` zurück.
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        """
        Initialisiert das Repository.
        
        Parameter:
            db (DatabaseProtocol): Datenbank-Adapter, über den alle SQL-Zugriffe laufen.
        """

        self.db = db

    def upsert(self, student: Student) -> int:
        """
        Legt einen Student an oder aktualisiert ihn (Upsert).
        
        Kurz:
            Schreibt Stammdaten in die DB. Existiert die Matrikelnummer bereits, wird der Datensatz
            aktualisiert (SQLite: `ON CONFLICT ... DO UPDATE`).
        
        Parameter:
            student (Student): Zu speicherndes Student-Objekt.
        
        Gibt zurück:
            int: Primärschlüssel `student_id` des gespeicherten Datensatzes.
        
        Fehler:
            RuntimeError: Wenn nach dem Upsert kein Datensatz gefunden werden kann (sollte nicht passieren).
        """

        cursor = self.db.execute(
            """
            INSERT INTO student(vorname, nachname, matrikelnummer, geburtsdatum, adresse)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(matrikelnummer) DO UPDATE SET
                vorname=excluded.vorname,
                nachname=excluded.nachname,
                geburtsdatum=excluded.geburtsdatum,
                adresse=excluded.adresse
            """,
            (
                student.vorname,
                student.nachname,
                student.matrikelnummer,
                _iso(student.geburtsdatum),
                student.adresse,
            ),
        )
        self.db.commit()

        # INSERT: lastrowid verfügbar; UPDATE: Fallback über SELECT
        # Nach INSERT ist `lastrowid` i. d. R. gesetzt. Falls nicht, nutzen wir SQLite-Fallback.
        if getattr(cursor, "lastrowid", None):
            return int(cursor.lastrowid)

        cursor = self.db.execute(
            "SELECT student_id FROM student WHERE matrikelnummer=?",
            (student.matrikelnummer,),
        )
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Student upsert failed: student not found after insert/update.")
        return int(row["student_id"])


class StudiengangRepository:
    """
    Repository für `Studiengang` (Persistenzzugriff).
    
    Kurz:
        Kapselt SQL-Zugriffe auf die Tabelle `studiengang` (Anlegen, Laden, Aktualisieren).
    
    Hinweis:
        Ein Student kann theoretisch mehrere Studiengänge besitzen.
        Für den Prototypen wird häufig der „aktuellste“ Studiengang verwendet
        (`ORDER BY studiengang_id DESC`).
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        """
        Initialisiert das Repository.
        
        Parameter:
            db (DatabaseProtocol): Datenbank-Adapter.
        """

        self.db = db

    def create(self, student_id: int, sg: Studiengang) -> int:
        """
        Legt einen Studiengang für einen Student an.
        
        Parameter:
            student_id (int): Referenz auf `student`.
            sg (Studiengang): Studiengang-Daten.
        
        Gibt zurück:
            int: Primärschlüssel `studiengang_id`.
        """

        cursor = self.db.execute(
            """
            INSERT INTO studiengang(
              student_id, name, start_datum, soll_studiensemester, soll_durchschnittsnote
            )
            VALUES(?,?,?,?,?)
            """,
            (
                student_id,
                sg.name,
                _iso(sg.start_datum),
                sg.soll_studiensemester,
                sg.soll_durchschnittsnote,
            ),
        )
        self.db.commit()

        # Nach INSERT ist `lastrowid` i. d. R. gesetzt. Falls nicht, nutzen wir SQLite-Fallback.
        if getattr(cursor, "lastrowid", None):
            return int(cursor.lastrowid)

        cursor = self.db.execute("SELECT last_insert_rowid() AS id")
        row = cursor.fetchone()
        return int(row["id"])

    def get_latest_for_student(self, student_id: int) -> Optional[tuple[int, Studiengang]]:
        """
        Lädt den zuletzt angelegten Studiengang eines Students.
        
        Kurz:
            Für den Prototypen wird meist nur mit dem aktuellsten Studiengang gearbeitet.
        
        Parameter:
            student_id (int): Primärschlüssel des Students.
        
        Gibt zurück:
            tuple[int, Studiengang] | None: (studiengang_id, Studiengang) oder `None` falls nicht vorhanden.
        """

        cursor = self.db.execute(
            """
            SELECT * FROM studiengang
            WHERE student_id=?
            ORDER BY studiengang_id DESC
            LIMIT 1
            """,
            (student_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        sg_id = int(row["studiengang_id"])
        sg = Studiengang(
            name=row["name"],
            start_datum=date.fromisoformat(row["start_datum"]),
            soll_studiensemester=int(row["soll_studiensemester"]) if row["soll_studiensemester"] is not None else None,
            soll_durchschnittsnote=float(row["soll_durchschnittsnote"]),
        )
        return sg_id, sg

    def update(self, studiengang_id: int, sg: Studiengang) -> None:
        """
        Aktualisiert die Stammdaten eines Studiengangs.
        
        Parameter:
            studiengang_id (int): Primärschlüssel des zu aktualisierenden Studiengangs.
            sg (Studiengang): Neue Werte.
        
        Hinweis:
            Es wird ein UPDATE ausgeführt; danach wird committet.
        """

        self.db.execute(
            """
            UPDATE studiengang SET
              name=?,
              start_datum=?,
              soll_studiensemester=?,
              soll_durchschnittsnote=?
            WHERE studiengang_id=?
            """,
            (
                sg.name,
                _iso(sg.start_datum),
                sg.soll_studiensemester,
                sg.soll_durchschnittsnote,
                studiengang_id,
            ),
        )
        self.db.commit()


class ModulRepository:
    """
    Repository für `Modul` (Modulkatalog).
    
    Kurz:
        Kapselt SQL-Zugriffe auf die Tabelle `modul` und bietet CRUD/Lookup-Operationen
        für die Modulauswahl in der GUI.
    
    Hinweis:
        Die UI zeigt Module typischerweise in stabiler Reihenfolge (nach `modul_id`).
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        """
        Initialisiert das Repository.
        
        Parameter:
            db (DatabaseProtocol): Datenbank-Adapter.
        """

        self.db = db

    def create(self, m: Modul) -> int:
        """
        Legt ein Modul im Modulkatalog an.
        
        Parameter:
            m (Modul): Modul-Stammdaten.
        
        Gibt zurück:
            int: Primärschlüssel `modul_id`.
        """

        cursor = self.db.execute(
            """
            INSERT INTO modul(titel, ects, plan_semester_nr, default_soll_bestanden_am)
            VALUES(?,?,?,?)
            """,
            (m.titel, m.ects, m.plan_semester_nr, _iso(m.default_soll_bestanden_am)),
        )
        self.db.commit()

        # Nach INSERT ist `lastrowid` i. d. R. gesetzt. Falls nicht, nutzen wir SQLite-Fallback.
        if getattr(cursor, "lastrowid", None):
            return int(cursor.lastrowid)

        cursor = self.db.execute("SELECT last_insert_rowid() AS id")
        row = cursor.fetchone()
        return int(row["id"])

    def update_by_id(self, modul_id: int, m: Modul) -> None:
        """
        Aktualisiert ein Modul anhand seiner `modul_id`.
        
        Parameter:
            modul_id (int): Primärschlüssel des Moduls.
            m (Modul): Neue Modulwerte.
        """

        self.db.execute(
            """
            UPDATE modul SET titel=?, ects=?, plan_semester_nr=?, default_soll_bestanden_am=?
            WHERE modul_id=?
            """,
            (m.titel, m.ects, m.plan_semester_nr, _iso(m.default_soll_bestanden_am), modul_id),
        )
        self.db.commit()

    def get_by_id(self, modul_id: int) -> Optional[Modul]:
        """
        Lädt ein Modul anhand seiner `modul_id`.
        
        Parameter:
            modul_id (int): Primärschlüssel des Moduls.
        
        Gibt zurück:
            Modul | None: Modul-Objekt oder `None`, wenn nicht gefunden.
        """

        cursor = self.db.execute("SELECT * FROM modul WHERE modul_id=?", (modul_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return Modul(
            modul_id=int(r["modul_id"]),
            titel=r["titel"],
            ects=int(r["ects"]),
            plan_semester_nr=int(r["plan_semester_nr"]),
            default_soll_bestanden_am=date.fromisoformat(r["default_soll_bestanden_am"]) if r["default_soll_bestanden_am"] else None,
        )

    def get_by_title(self, titel: str) -> Optional[Modul]:
        """
        Lädt ein Modul anhand seines Titels.
        
        Parameter:
            titel (str): Eindeutiger Modultitel.
        
        Gibt zurück:
            Modul | None: Modul-Objekt oder `None`.
        """

        cursor = self.db.execute("SELECT * FROM modul WHERE titel=?", (titel,))
        r = cursor.fetchone()
        if not r:
            return None
        return Modul(
            modul_id=int(r["modul_id"]),
            titel=r["titel"],
            ects=int(r["ects"]),
            plan_semester_nr=int(r["plan_semester_nr"]),
            default_soll_bestanden_am=date.fromisoformat(r["default_soll_bestanden_am"]) if r["default_soll_bestanden_am"] else None,
        )

    def list_all(self) -> list[Any]:
        # Stabile Sortierung für UI und KPI-Plots: nach Modul-Primärschlüssel sortieren.
        # Damit sind Combobox und Diagramme reproduzierbar nach Modul-ID sortiert.
        """
        Listet alle Module (für UI-Auswahl).
        
        Gibt zurück:
            list[Any]: Liste von Row-Objekten (sqlite3.Row) in stabiler Reihenfolge.
        """

        cursor = self.db.execute("SELECT * FROM modul ORDER BY modul_id ASC")
        return list(cursor.fetchall())

    def get_total_ects(self) -> float:
        """
        Summiert alle ECTS aus der Modultabelle.
        
        Kurz:
            Wird als Fallback genutzt, wenn kein Soll-Semester-Ziel für die Ziel-ECTS bekannt ist.
        
        Gibt zurück:
            float: Summe der ECTS (0.0 wenn keine Module angelegt sind).
        """

        cursor = self.db.execute("SELECT COALESCE(SUM(ects),0) AS s FROM modul")
        row = cursor.fetchone()
        return float(row["s"])


class ModulBelegungRepository:
    """
    Repository für `ModulBelegung` (Prüfungs-/Ist-Daten).
    
    Kurz:
        Kapselt SQL-Zugriffe auf die Tabelle `modul_belegung` (CRUD).
        Zusätzlich stellt es gezielte Query-Methoden für KPI-Berechnung und Diagramme bereit
        (z. B. ECTS-Summen, gewichtete Durchschnittsnote, Zeitreihen).
    
    Hinweis:
        Die meisten Methoden arbeiten studiengangbezogen, damit Daten sauber getrennt bleiben.
    """

    def __init__(self, db: DatabaseProtocol) -> None:
        """
        Initialisiert das Repository.
        
        Parameter:
            db (DatabaseProtocol): Datenbank-Adapter.
        """

        self.db = db

    def create(self, b: ModulBelegung) -> int:
        """
        Legt eine neue Modulbelegung an (INSERT).
        
        Parameter:
            b (ModulBelegung): Belegungsdaten.
        
        Gibt zurück:
            int: Primärschlüssel `belegung_id` der neu angelegten Belegung.
        """

        cursor = self.db.execute(
            """
            INSERT INTO modul_belegung(
              studiengang_id, modul_id, plan_semester_nr, ist_semester_nr,
              soll_bestanden_am, ist_bestanden_am, soll_note, ist_note, anzahl_versuche
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                b.studiengang_id,
                b.modul_id,
                b.plan_semester_nr,
                b.ist_semester_nr,
                _iso(b.soll_bestanden_am),
                _iso(b.ist_bestanden_am),
                b.soll_note,
                b.ist_note,
                b.anzahl_versuche,
            ),
        )
        self.db.commit()

        # Nach INSERT ist `lastrowid` i. d. R. gesetzt. Falls nicht, nutzen wir SQLite-Fallback.
        if getattr(cursor, "lastrowid", None):
            return int(cursor.lastrowid)

        cursor = self.db.execute("SELECT last_insert_rowid() AS id")
        row = cursor.fetchone()
        return int(row["id"])

    def get(self, studiengang_id: int, belegung_id: int) -> Optional[ModulBelegung]:
        """
        Lädt eine Modulbelegung anhand von Studiengang und Belegungs-ID.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            belegung_id (int): Primärschlüssel der Belegung.
        
        Gibt zurück:
            ModulBelegung | None: Belegung oder `None`.
        """

        cursor = self.db.execute(
            "SELECT * FROM modul_belegung WHERE studiengang_id=? AND belegung_id=?",
            (studiengang_id, belegung_id),
        )
        r = cursor.fetchone()
        if not r:
            return None
        return ModulBelegung(
            belegung_id=int(r["belegung_id"]),
            studiengang_id=int(r["studiengang_id"]),
            modul_id=int(r["modul_id"]),
            plan_semester_nr=int(r["plan_semester_nr"]),
            ist_semester_nr=int(r["ist_semester_nr"]) if r["ist_semester_nr"] is not None else None,
            soll_bestanden_am=date.fromisoformat(r["soll_bestanden_am"]) if r["soll_bestanden_am"] else None,
            ist_bestanden_am=date.fromisoformat(r["ist_bestanden_am"]) if r["ist_bestanden_am"] else None,
            soll_note=float(r["soll_note"]) if r["soll_note"] is not None else None,
            ist_note=float(r["ist_note"]) if r["ist_note"] is not None else None,
            anzahl_versuche=int(r["anzahl_versuche"]),
        )

    def update(self, b: ModulBelegung) -> None:
        """
        Aktualisiert eine bestehende Modulbelegung.
        
        Parameter:
            b (ModulBelegung): Belegung mit gesetzter `belegung_id`.
        
        Fehler:
            ValueError: Wenn `belegung_id` nicht gesetzt ist.
        """

        if b.belegung_id is None:
            raise ValueError("belegung_id required for update")
        self.db.execute(
            """
            UPDATE modul_belegung SET
              modul_id=?,
              plan_semester_nr=?,
              ist_semester_nr=?,
              soll_bestanden_am=?,
              ist_bestanden_am=?,
              soll_note=?,
              ist_note=?,
              anzahl_versuche=?
            WHERE studiengang_id=? AND belegung_id=?
            """,
            (
                b.modul_id,
                b.plan_semester_nr,
                b.ist_semester_nr,
                _iso(b.soll_bestanden_am),
                _iso(b.ist_bestanden_am),
                b.soll_note,
                b.ist_note,
                b.anzahl_versuche,
                b.studiengang_id,
                b.belegung_id,
            ),
        )
        self.db.commit()

    def delete(self, studiengang_id: int, belegung_id: int) -> None:
        """
        Löscht eine Modulbelegung.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            belegung_id (int): Primärschlüssel der Belegung.
        """

        self.db.execute(
            "DELETE FROM modul_belegung WHERE studiengang_id=? AND belegung_id=?",
            (studiengang_id, belegung_id),
        )
        self.db.commit()

    def list_latest(self, studiengang_id: int, limit: int = 200) -> list[Any]:
        """
        Listet die zuletzt angelegten Belegungen (für die Tabelle in der UI).
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
            limit (int): Maximale Anzahl zurückgegebener Zeilen.
        
        Gibt zurück:
            list[Any]: Row-Objekte mit Joins auf Modultitel/ECTS.
        """

        cursor = self.db.execute(
            """
            SELECT
              mb.belegung_id,
              mb.modul_id,
              m.titel AS modul_titel,
              m.ects AS ects,
              mb.plan_semester_nr,
              mb.ist_semester_nr,
              mb.ist_bestanden_am,
              mb.ist_note,
              mb.soll_note,
              mb.anzahl_versuche
            FROM modul_belegung mb
            JOIN modul m ON m.modul_id = mb.modul_id
            WHERE mb.studiengang_id=?
            ORDER BY mb.belegung_id DESC
            LIMIT ?
            """,
            (studiengang_id, limit),
        )
        return list(cursor.fetchall())

    # ---------- KPI helper queries ----------
    def sum_ects_completed(self, studiengang_id: int) -> float:
        """
        Summiert die ECTS aller bestandenen Module.
        
        Kurz:
            Zählt ECTS nur dann, wenn `ist_bestanden_am` gesetzt ist.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Gibt zurück:
            float: Summe bestandener ECTS.
        """

        cursor = self.db.execute(
            """
            SELECT COALESCE(SUM(m.ects),0) AS ects
            FROM modul_belegung mb
            JOIN modul m ON m.modul_id = mb.modul_id
            WHERE mb.studiengang_id=?
              AND mb.ist_bestanden_am IS NOT NULL
            """,
            (studiengang_id,),
        )
        row = cursor.fetchone()
        return float(row["ects"])

    def avg_grade_weighted(self, studiengang_id: int) -> Optional[float]:
        """
        Berechnet die ECTS-gewichtete Durchschnittsnote.
        
        Kurz:
            Mittelt alle vorhandenen `ist_note`-Werte über ECTS-Gewichtung:
            Summe(ECTS * Note) / Summe(ECTS).
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Gibt zurück:
            float | None: Gewichtete Durchschnittsnote oder `None`, wenn keine Noten vorliegen.
        """

        cursor = self.db.execute(
            """
            SELECT
              SUM(m.ects * mb.ist_note) AS wsum,
              SUM(m.ects) AS ects
            FROM modul_belegung mb
            JOIN modul m ON m.modul_id = mb.modul_id
            WHERE mb.studiengang_id=?
              AND mb.ist_note IS NOT NULL
            """,
            (studiengang_id,),
        )
        row = cursor.fetchone()
        if not row or row["ects"] in (None, 0):
            return None
        return float(row["wsum"]) / float(row["ects"])

    def last_completion_date(self, studiengang_id: int) -> Optional[date]:
        """
        Ermittelt das Datum der zuletzt bestandenen Prüfung.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Gibt zurück:
            date | None: Maximales `ist_bestanden_am` oder `None`.
        """

        cursor = self.db.execute(
            """
            SELECT MAX(ist_bestanden_am) AS last_date
            FROM modul_belegung
            WHERE studiengang_id=?
              AND ist_bestanden_am IS NOT NULL
            """,
            (studiengang_id,),
        )
        row = cursor.fetchone()
        if not row or not row["last_date"]:
            return None
        return date.fromisoformat(row["last_date"])

    # ---------- Plot helper queries ----------
    def plot_latest_per_module(self, studiengang_id: int) -> list[Any]:
        """
        Liefert den jeweils neuesten Datensatz je Modul (für Diagramme).
        
        Kurz:
            Für jedes Modul wird die letzte Belegung (höchste `belegung_id`) ermittelt und
            um Stammdaten (Titel/ECTS) ergänzt. Damit können Soll-/Ist-Noten sowie Zeitabweichungen
            pro Modul geplottet werden.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Gibt zurück:
            list[Any]: Row-Objekte (sqlite3.Row) mit Feldern wie `titel`, `soll_note`, `ist_note`,
            `soll_bestanden_am`, `ist_bestanden_am` und `delta_days`.
        
        Hinweis:
            Implementierung ist SQLite-kompatibel (ohne Window Functions).
        """

        cursor = self.db.execute(
            """
            WITH latest AS (
              SELECT MAX(belegung_id) AS last_id, modul_id
              FROM modul_belegung
              WHERE studiengang_id=?
              GROUP BY modul_id
            )
            SELECT
              mb.modul_id AS modul_id,
              m.titel AS titel,
              m.ects AS ects,
              mb.soll_note AS soll_note,
              mb.ist_note AS ist_note,
              mb.soll_bestanden_am AS soll_bestanden_am,
              mb.ist_bestanden_am AS ist_bestanden_am,
              CASE
                WHEN mb.soll_bestanden_am IS NOT NULL AND mb.ist_bestanden_am IS NOT NULL
                THEN CAST((julianday(mb.ist_bestanden_am) - julianday(mb.soll_bestanden_am)) AS INTEGER)
                ELSE NULL
              END AS delta_days
            FROM latest l
            JOIN modul_belegung mb ON mb.belegung_id = l.last_id
            JOIN modul m ON m.modul_id = mb.modul_id
            -- Reihenfolge konsistent zur UI halten: nach Modul-ID sortieren.
            ORDER BY m.modul_id ASC
            """,
            (studiengang_id,),
        )
        return list(cursor.fetchall())

    def plot_completions(self, studiengang_id: int) -> list[Any]:
        """
        Liefert Zeitreihendaten für ECTS-/Noten-Verlauf.
        
        Kurz:
            Stellt Datensätze bereit, die nach Bestehensdatum sortiert sind und sich für
            kumulative ECTS sowie Durchschnittsnote über die Zeit eignen.
        
        Parameter:
            studiengang_id (int): Kontext-Studiengang.
        
        Gibt zurück:
            list[Any]: Row-Objekte mit `ist_bestanden_am`, `ects` und `ist_note`.
        """

        cursor = self.db.execute(
            """
            SELECT
              mb.ist_bestanden_am AS ist_bestanden_am,
              m.ects AS ects,
              mb.ist_note AS ist_note
            FROM modul_belegung mb
            JOIN modul m ON m.modul_id = mb.modul_id
            WHERE mb.studiengang_id = ?
              AND mb.ist_bestanden_am IS NOT NULL
            ORDER BY mb.ist_bestanden_am ASC, mb.belegung_id ASC
            """,
            (studiengang_id,),
        )
        return list(cursor.fetchall())