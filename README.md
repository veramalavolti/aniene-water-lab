# Aniene Water Lab

Piattaforma pubblica per esplorare i risultati del monitoraggio civico della qualità dell'acqua del fiume Aniene: 1.041 misure, 9 stazioni e 22 campagne da aprile 2022 a ottobre 2024.

- `dist/index.html`: il progetto, gli strumenti, i parametri e la metodologia
- `dist/risultati.html`: i risultati raccontati in sei domande
- `dist/dashboard.html`: mappa, profilo da monte a valle, andamento, matrice, statistiche ed export CSV

Il sito è statico, stile e logo vengono dalla [dashboard del Fosso Galeria](https://github.com/veramalavolti/fosso-galeria-2020-2025).

## Dati

| Periodo | Fonte | Contenuto |
| --- | --- | --- |
| Dic 2023 – ott 2024 | Excel `Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx`, foglio Dati | 91 campioni e 11 rilievi straordinari |
| Apr 2022 – mar 2023 | Punti dei grafici vettoriali della relazione di Bruna Gumiero | 55 campioni, 5 parametri |

L'Excel e il PDF non sono nel repository: per rigenerare i dati servono i file originali. Tutte le misure sono in `dist/aniene_dati.csv`, e il registro delle modifiche all'Excel è nel campo `corrections` di `dist/data.json`.

    python3 scripts/extract_report_charts.py "relazione.pdf"   # richiede PyMuPDF
    python3 scripts/import_data.py "dataset.xlsx"              # richiede openpyxl
    python3 scripts/test_data.py

Il corso del fiume in `dist/fiumi.geojson` viene da OpenStreetMap (© contributori OpenStreetMap, ODbL).
