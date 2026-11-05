# Aniene Water Lab

Piattaforma pubblica per esplorare i risultati del monitoraggio civico della qualità dell'acqua del fiume Aniene: 1.281 misure, 10 stazioni e 25 campagne da aprile 2022 a dicembre 2025.

- `dist/index.html`: il progetto, gli strumenti, i parametri e la metodologia
- `dist/risultati.html`: i risultati raccontati in sei domande
- `dist/dashboard.html`: mappa, profilo da monte a valle, andamento, matrice, statistiche ed export CSV

Il sito è statico, stile e logo vengono dalla [dashboard del Fosso Galeria](https://github.com/veramalavolti/fosso-galeria-2020-2025).

## Dati

| Periodo | Fonte | Contenuto |
| --- | --- | --- |
| Dic 2023 – ott 2024 | Excel `Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx`, foglio Dati | 91 campioni e 11 rilievi straordinari |
| Ott – dic 2025 | Excel `Dati campionamento Aniene 2025-2026.xlsx`, foglio Dati 9 punti | 27 campioni, solo le tre campagne del 2025 |
| Apr 2022 – mar 2023 | Punti dei grafici vettoriali della relazione di Bruna Gumiero | 55 campioni, 5 parametri |

I file Excel e il PDF non sono nel repository: per rigenerare i dati servono i file originali. Tutte le misure sono in `dist/aniene_dati.csv`, e il registro delle modifiche all'Excel è nel campo `corrections` di `dist/data.json`.

    python3 scripts/extract_report_charts.py "relazione.pdf"   # richiede PyMuPDF
    python3 scripts/import_data.py "dataset_23_24.xlsx" "dati_2025_2026.xlsx"   # richiede openpyxl
    python3 scripts/test_data.py

Il corso del fiume in `dist/fiumi.geojson` viene da OpenStreetMap (© contributori OpenStreetMap, ODbL).
