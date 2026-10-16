Greek Parallel Reader v6.2: visible word-inspection popup.
Copy server.py over ~/GREEK-LIBRARY/greek_alignment_fix/server.py, or run directly from this folder.
Uses existing data/alignments_v6.db and data/scholarly.db; does not rebuild them.
Start: python3 server.py --base ~/GREEK-LIBRARY --host 0.0.0.0 --port 8799
Open: http://family.local:8799/?q=magus
Click a Greek word to open a floating LSJ card; click a suggestion to look that word up. Escape or × closes the card.
