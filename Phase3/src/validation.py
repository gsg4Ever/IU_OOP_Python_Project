"""Parsing/Validierung für GUI-Eingaben.

Die GUI liefert alles als Text. Dieses Modul wandelt Strings in passende Python-Typen
(int/float/date) um und macht ein paar einfache Plausibilitätschecks, damit keine völlig
kaputten Werte in Service/Repository landen.

Datumsformate, die akzeptiert werden:
- YYYY-MM-DD
- DD.MM.YY
- DD.MM.YYYY
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


class ValidationError(ValueError):
    """
    Fehlerklasse für ungültige Benutzereingaben.
    
    Kurz:
        Wird in der UI abgefangen, um eine verständliche Fehlermeldung anzuzeigen,
        ohne einen technischen Traceback zu präsentieren.
    """


def parse_date(text: str) -> Optional[date]:
    """
    Parst ein Datum aus typischen Eingabeformaten.
    
    Kurz:
        Unterstützt mehrere Datumsformate, damit Nutzer:innen flexibel eingeben können.
    
    Parameter:
        text (str): Eingabetext (z. B. aus einem Entry-Feld).
    
    Gibt zurück:
        date | None: Geparstes Datum oder `None` bei leerer Eingabe.
    
    Fehler:
        ValidationError: Wenn kein unterstütztes Format erkannt wird.
    
    Hinweis:
        Unterstützte Formate:
        - YYYY-MM-DD (ISO)
        - DD.MM.YY
        - DD.MM.YYYY
    """

    t = (text or "").strip()
    if not t:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    raise ValidationError("Datum muss YYYY-MM-DD oder DD.MM.YY(YY) sein")


def parse_int(text: str, *, field: str, min_value: Optional[int] = None) -> int:
    """
    Parst eine Ganzzahl aus einem Eingabefeld.
    
    Kurz:
        Wandelt den Text in `int` um und prüft optional einen Minimalwert.
    
    Parameter:
        text (str): Eingabetext.
        field (str): Feldname für verständliche Fehlermeldungen.
        min_value (int | None): Optionaler Minimalwert.
    
    Gibt zurück:
        int: Geparste Ganzzahl.
    
    Fehler:
        ValidationError: Bei nicht numerischer Eingabe oder Unterschreitung von `min_value`.
    """

    try:
        v = int(str(text).strip())
    except Exception as exc:
        raise ValidationError(f"{field} muss eine ganze Zahl sein") from exc
    if min_value is not None and v < min_value:
        raise ValidationError(f"{field} muss >= {min_value} sein")
    return v


def parse_float(text: str, *, field: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    """
    Parst eine Fließkommazahl (Komma oder Punkt).
    
    Kurz:
        Wandelt den Text in `float` um (`,` wird als Dezimaltrennzeichen akzeptiert) und
        prüft optional einen Wertebereich.
    
    Parameter:
        text (str): Eingabetext.
        field (str): Feldname für Fehlermeldungen.
        min_value (float | None): Untere Schranke (optional).
        max_value (float | None): Obere Schranke (optional).
    
    Gibt zurück:
        float: Geparste Zahl.
    
    Fehler:
        ValidationError: Bei ungültiger Eingabe oder Verletzung des Wertebereichs.
    """

    try:
        v = float(str(text).strip().replace(",", "."))
    except Exception as exc:
        raise ValidationError(f"{field} muss eine Zahl sein") from exc
    if min_value is not None and v < min_value:
        raise ValidationError(f"{field} muss >= {min_value} sein")
    if max_value is not None and v > max_value:
        raise ValidationError(f"{field} muss <= {max_value} sein")
    return v




def parse_optional_int(text: str, *, field: str, min_value: Optional[int] = None) -> Optional[int]:
    """
    Parst eine optionale Ganzzahl.
    
    Kurz:
        Leere Eingaben werden als `None` interpretiert (z. B. für optionale Felder wie
        Ist-Semester). Nicht-leere Eingaben werden wie bei `parse_int` geprüft.
    
    Parameter:
        text (str): Eingabetext.
        field (str): Feldname für Fehlermeldungen.
        min_value (int | None): Optionaler Minimalwert.
    
    Gibt zurück:
        int | None: Geparste Zahl oder `None`.
    """

    t = (text or "").strip()
    if not t:
        return None
    return parse_int(t, field=field, min_value=min_value)


def parse_optional_float(
    text: str, *, field: str, min_value: Optional[float] = None, max_value: Optional[float] = None
) -> Optional[float]:
    """
    Parst eine optionale Fließkommazahl.
    
    Kurz:
        Leere Eingaben werden als `None` interpretiert (z. B. für Soll-/Ist-Noten).
        Nicht-leere Eingaben werden wie bei `parse_float` geprüft.
    
    Parameter:
        text (str): Eingabetext.
        field (str): Feldname für Fehlermeldungen.
        min_value (float | None): Untere Schranke (optional).
        max_value (float | None): Obere Schranke (optional).
    
    Gibt zurück:
        float | None: Geparste Zahl oder `None`.
    """

    t = (text or "").strip()
    if not t:
        return None
    return parse_float(t, field=field, min_value=min_value, max_value=max_value)


def validate_grade(grade: Optional[float]) -> None:
    """
    Validiert einen Notenwert (vereinfachter Prototyp-Range).
    
    Kurz:
        Im Prototyp wird ein einfacher Wertebereich von 1.0 bis 5.0 angenommen.
    
    Parameter:
        grade (float | None): Note oder `None`.
    
    Fehler:
        ValidationError: Wenn `grade` außerhalb des zulässigen Bereichs liegt.
    """

    if grade is None:
        return
    if not (1.0 <= grade <= 5.0):
        raise ValidationError("Note muss zwischen 1.0 und 5.0 liegen")


def validate_attempts(attempts: int) -> None:
    """
    Validiert die Anzahl der Prüfungsversuche.
    
    Kurz:
        Stellt sicher, dass die Anzahl der Versuche mindestens 1 ist.
    
    Parameter:
        attempts (int): Anzahl Versuche.
    
    Fehler:
        ValidationError: Wenn `attempts < 1`.
    """

    if attempts < 1:
        raise ValidationError("Anzahl Versuche muss >= 1 sein")