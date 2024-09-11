# KI-gestütztes Recherchesystem

Dieses Projekt ist ein KI-gestütztes Recherchesystem, das es Benutzern ermöglicht, Fragen zu stellen und Antworten basierend auf einer vordefinierten Wissensbasis zu erhalten. Es unterstützt mehrere Benutzeroberflächen und kann für verschiedene Anwendungsfälle konfiguriert werden.

## Funktionen

- Benutzerauthentifizierung und -verwaltung
- Dashboard zur Verwaltung von Textbasen und Systemeinstellungen
- Frage-Antwort-System mit KI-Unterstützung
- Unterstützung für mehrere Sprach- und Benutzeroberflächen-Konfigurationen
- Integration mit Azure OpenAI und Ollama für Textgenerierung
- Möglichkeit zum Import von Dokumenten aus SharePoint

## Technologie-Stack

- Backend: Flask (Python)
- Frontend: HTML, JavaScript, Tailwind CSS
- Datenbank: SQLite mit SQLAlchemy ORM
- KI-Dienste: Azure OpenAI, Ollama
- Vektordatenbank: Chroma

## Installation

1. Klonen Sie das Repository:
   ```
   git clone [repository-url]
   ```

2. Installieren Sie die erforderlichen Python-Pakete:
   ```
   pip install -r requirements.txt
   ```

3. Erstellen Sie eine `.env`-Datei im Hauptverzeichnis und fügen Sie die erforderlichen Umgebungsvariablen hinzu:
   ```
   SECRET_KEY=your_secret_key
   AZURE_OPENAI_KEY=your_azure_openai_key
   AZURE_ENDPOINT=your_azure_endpoint
   AZURE_MODEL=your_azure_model
   AZURE_EMBEDDING_MODEL=your_azure_embedding_model
   OLLAMA_MODEL=your_ollama_model
   LABEL_OWNER=your_label_owner
   ```

4. Initialisieren Sie die Datenbank:
   ```
   flask db upgrade
   ```

## Verwendung

1. Starten Sie die Flask-Anwendung:
   ```
   flask run
   ```

2. Öffnen Sie einen Webbrowser und navigieren Sie zu `http://localhost:5000`

3. Melden Sie sich mit den Standardanmeldeinformationen an (falls vorhanden) oder erstellen Sie einen neuen Benutzer.

4. Verwenden Sie das Dashboard, um Textbasen zu erstellen und zu verwalten.

5. Stellen Sie Fragen und erhalten Sie KI-generierte Antworten basierend auf der ausgewählten Textbasis.

## Anpassung

- Benutzeroberfläche: Die Benutzeroberfläche kann durch Ändern der Labels in den JSON-Dateien im `labels`-Verzeichnis angepasst werden. Siehe:
