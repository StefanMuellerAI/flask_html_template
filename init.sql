-- Erstelle die Tabelle für Benutzer
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(20) NOT NULL UNIQUE,
    password VARCHAR(60) NOT NULL
);

-- Erstelle die Tabelle für Kollektionen
CREATE TABLE IF NOT EXISTS collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

-- Erstelle die Tabelle für Dateien
CREATE TABLE IF NOT EXISTS file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(100) NOT NULL,
    collection_id INTEGER NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collection(id) ON DELETE CASCADE
);

-- Erstelle die Tabelle für System-Prompts
CREATE TABLE IF NOT EXISTS system_prompt (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

-- Erstelle die Tabelle für Konversationen
CREATE TABLE IF NOT EXISTS conversation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    system_prompt_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (system_prompt_id) REFERENCES system_prompt(id) ON DELETE SET NULL
);

-- Füge einen Admin-Benutzer hinzu
INSERT INTO user (username, password) VALUES ('admin', 'scrypt:32768:8:1$L7f2rNpVLtfsrPwn$9ecf71606f29c2b96038787beb975e24c52adc15fe0f4cbb60392d6e82588af8f657e3ea06360ee645b30d250af451c0abc445f300c1a0f16bbfc13beffb0006');
