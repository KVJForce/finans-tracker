# Finans Tracker

En modern desktop-applikation för personlig ekonomihantering, byggd i Python med CustomTkinter.

## Funktioner

- **Dashboard** – Total balans, månadens inkomster/utgifter och cirkeldiagram per kategori
- **Transaktioner** – Lägg till, redigera och ta bort inkomster/utgifter med filtrering
- **Import** – Läs in bank-CSV med förhandsgranskning, automatisk kategorisering och dubblettskydd
- **Kategorier** – Egna kategorier med färgkodning
- **Datalagring** – SQLite-databas med automatisk daglig backup
- **Export** – Exportera transaktioner till CSV
- **Tema** – Växla mellan mörkt och ljust läge

## Krav

- Python 3.10 eller senare
- Windows, macOS eller Linux

## Installation

1. Klona eller ladda ner projektet:

```bash
cd finans-tracker
```

2. Skapa och aktivera en virtuell miljö (rekommenderas):

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

3. Installera beroenden:

```bash
pip install -r requirements.txt
```

## Starta applikationen

```bash
python main.py
```

## Importera bank-CSV

1. Öppna **Transaktioner** och klicka på **Importera CSV**.
2. Välj en CSV-export från din bank.
3. Kontrollera förhandsvisningen. Dubbelklicka på en rad för att byta kategori.
4. Klicka på **Importera**.

![Förhandsvisning av CSV-import](docs/import-preview.png)

Importen:

- hittar rubrikraden även om filen har inledande rader med kontoinformation
- stödjer `;`, `,`, tabb och `|` som separator
- läser UTF-8, UTF-16 och CP1252 (vanligt i äldre svenska bankexporter)
- tolkar både svenska och engelska datum- och beloppsformat
- använder beloppets tecken när filen saknar en typkolumn
- hoppar över dubbletter baserat på datum, belopp, typ och beskrivning
- föreslår kategori med reglerna i `finans_tracker/importers/rules.py`

Två exempelfiler finns i `samples/`. Om samma köp förekommer två gånger i
filen importeras båda raderna, så länge de inte redan finns i databasen.

### Så fungerar importen

Importen är delad i tre steg för att vara lätt att testa utan gränssnitt:

1. `bank_csv.py` tolkar filen och skapar `ParsedTransaction`-objekt.
2. `service.py` markerar dubbletter och föreslår kategorier.
3. `import_dialog.py` visar förhandsvisningen och sparar raderna i en
   gemensam databastransaktion.

## Tester

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Testerna täcker belopps- och datumformat, kodningar, separatorer,
kategorisering, dubbletträkning och databasens bulkimport.

## Data och backup

All data sparas lokalt i:

- **Databas:** `~/.finans_tracker/finans.db`
- **Backups:** `~/.finans_tracker/backups/` (max 10 senaste kopior)

Automatisk backup sker vid uppstart (en gång per dag) och vid avslut.

## Projektstruktur

```
finans-tracker/
├── main.py                  # Startpunkt
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── samples/                 # Exempel på bank-CSV
├── tests/                   # Tester för importlogiken
└── finans_tracker/
    ├── app.py               # Huvudfönster
    ├── database.py          # SQLite-hantering
    ├── models.py            # Datamodeller
    ├── backup.py            # Säkerhetskopiering
    ├── export.py            # CSV-export
    ├── theme.py             # Temahantering
    ├── importers/
    │   ├── bank_csv.py      # Tolkning av CSV-filer
    │   ├── categorizer.py   # Automatisk kategorisering
    │   ├── normalize.py     # Belopp, datum och text
    │   ├── rules.py         # Kategoriseringsregler
    │   └── service.py       # Dubbletter och importflöde
    └── ui/
        ├── dashboard.py
        ├── transactions.py
        ├── import_dialog.py # Förhandsvisning av import
        ├── categories.py
        └── components.py
```

## Licens

MIT
