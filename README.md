# Aniene Water Lab

La piattaforma dei monitoraggi partecipati sul fiume Aniene: il percorso dal
2021 a oggi, la metodologia della citizen science, i dati aperti delle tre
campagne di monitoraggio con dashboard interattive, e i report da scaricare.

Il sito è statico: non ha un database né un pannello di amministrazione da
aggiornare, quindi è veloce, gratuito da ospitare e non richiede manutenzione
di sicurezza. I testi però non stanno dentro il codice, ma in file di contenuto
separati: chi cura il sito li modifica da un pannello di redazione, in
italiano, senza toccare una riga di codice.

## Le pagine

| Pagina | Cosa contiene |
| --- | --- |
| `index` | Il fiume, il progetto, il Contratto di Fiume, la citizen science, gli obiettivi |
| `citizen-science` | La scienza partecipata, le schede dei parametri, la metodologia, i macroinvertebrati |
| `campagna-2022-2023` | Walk Up Aniene e RomaUp, 5 stazioni urbane, dashboard, report |
| `campagna-2023-2024` | Aniene WaterLab, 9 stazioni da Subiaco al Tevere, dashboard, report |
| `campagna-2025-2026` | Punti fissi e campagne in gommone, due dashboard, hotspot, report |
| `contatti` | La rete dei partner, il modulo di segnalazione, il bollettino dell'Aniene |

## Modificare i testi senza programmare

1. Vai su [app.pagescms.org](https://app.pagescms.org) ed entra con il tuo
   account GitHub.
2. Apri questo repository: trovi una voce per ogni pagina del sito.
3. Modifica i campi (titolo, paragrafi, schede, didascalie…) e salva.
4. Dopo un paio di minuti il sito pubblicato è aggiornato.

Il pannello mostra solo i campi previsti, descritti in `.pages.yml`: non è
possibile rompere il layout. Le fotografie si caricano dallo stesso pannello e
finiscono in `assets/img/foto`, i report in `dist/report`.

Chi preferisce può modificare direttamente i file in `contenuti/`: sono file di
testo con un campo per riga, con i commenti che spiegano a cosa serve ciascuno.

## Com'è fatto

    contenuti/      i testi, uno per pagina, più i parametri e le impostazioni
    dati/           i dati delle campagne in JSON, generati dagli Excel
    templates/      la struttura HTML delle pagine
    assets/         CSS, JavaScript, fotografie, loghi
    scripts/        l'estrazione dei dati dagli Excel originali
    build.py        costruisce dist/ unendo contenuti, dati e templates
    dist/           il sito pubblicato: generato, tranne dist/report con i PDF

### Parametri e soglie

`contenuti/parametri.yml` è il cuore delle dashboard: per ogni parametro
contiene nome, unità di misura, che cosa misura, come si legge e le soglie.
Ogni soglia ha il valore a cui viene disegnata la linea, l'etichetta sempre
visibile accanto alla linea, la spiegazione di che cosa significa superarla e
le possibili cause, che compaiono passando il mouse sulla linea. Le stesse
schede alimentano anche le pagine dei parametri, quindi una correzione fatta lì
si riflette ovunque.

## Rigenerare il sito

    pip install pyyaml jinja2
    python3 build.py

Per rigenerare i dati dagli Excel originali (che non stanno nel repository, ma
nella cartella di progetto «Aniene»):

    pip install openpyxl
    python3 scripts/estrai_dati.py --sorgente "/percorso/della/cartella/Aniene"

Per vedere il sito in locale:

    python3 -m http.server 4173 --directory dist

## Pubblicazione

Il sito sta su **GitHub Pages**, all'indirizzo
`https://veramalavolti.github.io/aniene-water-lab/`. L'indirizzo è pubblico:
chiunque abbia il link può aprirlo, senza account né password.

Il flusso `.github/workflows/pubblica.yml` fa tutto a ogni push su `main` che
tocchi contenuti, modelli, fogli di stile o dati: ricostruisce `dist/`, lo
rimette nel repository e lo pubblica su Pages. Non serve collegare servizi
esterni — il sito vive nello stesso repository dei contenuti, quindi non c'è
nessuna autorizzazione da rinnovare.

Le pagine usano solo percorsi relativi, perciò funzionano anche servite da una
sottocartella come fa Pages.

`vercel.json` resta nel repository: serve soltanto se un giorno si vuole
pubblicare anche su Vercel. Attenzione, in quel caso, che l'app Vercel su GitHub
dev'essere installata sull'account **proprietario del repository**: se è
installata su un altro account vede «Connected» ma non riceve i push, e non
ricostruisce mai.

### Accesso a GitHub

Il repository si aggiorna via SSH, non con i token: la chiave sta in
`~/.ssh/id_ed25519` sul computer di chi pubblica e la parte pubblica è
registrata su GitHub. I token di accesso personali non servono e non vanno
incollati da nessuna parte — un token con permesso `repo` vale quanto la
password di tutti i repository.

## Dati e fonti

| Campagna | Fonte | Contenuto |
| --- | --- | --- |
| 2022-2023 | `Dati-Tevere-e-Aniene22-23.xlsx`, foglio `dati_grezzi` | 5 stazioni sull'Aniene, 11 campagne, 55 prelievi |
| 2023-2024 | `Dataset definitivo … 23_24.xlsx`, foglio `Dataset` | 9 stazioni, 11 campagne, 91 prelievi |
| 2023-2024 gommone | stesso file, punti 10-14 | 5 punti, 2 discese |
| 2025-2026 | `Dataset … 25_26.xlsx`, foglio `Dataset 9 punti` | 9 stazioni, 13 campagne, 116 prelievi |
| 2025-2026 gommone | `Dati campionamento Aniene 2025-2026.xlsx`, foglio `Dati gommone` | 34 punti (27 numerati più i BIS), 5 uscite |
| 2025-2026 asta | stesso file, foglio `Extra ogni 3km circa` | 13 punti lungo l'asta |

La supervisione scientifica dei dati è di Bruna Gumiero, ecologa fluviale
dell'Università di Bologna.

Testi e dati sono rilasciati con licenza Creative Commons BY-SA 4.0. Le
fotografie appartengono a chi le ha scattate.
