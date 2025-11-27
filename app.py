import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile
import os
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BN3500 Converter (Cloud DB)", layout="wide")

# --- POŁĄCZENIE Z GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data_from_sheet():
    """Pobiera dane z Google Sheets i konwertuje na słownik."""
    try:
        # Czytamy arkusz (domyślnie pierwszy)
        df = conn.read(usecols=[0, 1], ttl=0)  # ttl=0 żeby nie cache'owało starych danych
        df = df.dropna() # Usuń puste wiersze
        
        # Konwersja DataFrame na słownik: {'Moduł': ['CZ1', 'CZ2']}
        db = {}
        for index, row in df.iterrows():
            module = row[0] # Kolumna A
            cz_raw = row[1] # Kolumna B
            
            # Zakładamy, że w Excelu numery CZ są oddzielone średnikiem
            if isinstance(cz_raw, str):
                cz_list = [x.strip() for x in cz_raw.split(';') if x.strip()]
            else:
                cz_list = [str(cz_raw)]
                
            db[module] = cz_list
        return db, df
    except Exception as e:
        st.error(f"Nie udało się połączyć z bazą Google Sheets: {e}")
        return {}, pd.DataFrame(columns=["Module", "CZ"])

def save_data_to_sheet(updated_df):
    """Zapisuje DataFrame z powrotem do Google Sheets."""
    try:
        conn.update(data=updated_df)
        st.cache_data.clear() # Wyczyść cache
        st.success("Baza zapisana w chmurze Google!")
    except Exception as e:
        st.error(f"Błąd zapisu do chmury: {e}")

# --- UI ---

st.title("☁️ BN3500 Converter + Google Sheets DB")

# Ładowanie danych przy starcie
if 'cz_db' not in st.session_state:
    db_dict, db_df = load_data_from_sheet()
    st.session_state['cz_db'] = db_dict
    st.session_state['cz_df'] = db_df

tab1, tab2 = st.tabs(["📄 Konwerter", "🛠️ Baza Danych (Google Sheets)"])

# --- ZAKŁADKA 1: KONWERTER (Bez zmian w logice, tylko używa session_state) ---
with tab1:
    uploaded_files = st.file_uploader("Wybierz PDF", type="pdf", accept_multiple_files=True)
    
    if uploaded_files and st.button("Przetwórz"):
        # (Tu wklej ten sam kod przetwarzania PDF co wcześniej)
        # Używając: current_db = st.session_state['cz_db']
        # ... (skrót dla czytelności, logika ta sama)
        
        # Prosty przykład działania dla testu:
        current_db = st.session_state['cz_db']
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for uploaded_file in uploaded_files:
                # --- TUTAJ CAŁA TWOJA LOGIKA PARSOWANIA PDF ---
                # Poniżej tylko symulacja:
                name = uploaded_file.name
                result_text = "Przykładowy wynik na podstawie bazy:\n"
                for mod, czs in current_db.items():
                     result_text += f"{mod}: {czs}\n"
                # ----------------------------------------------
                
                zip_file.writestr(f"{name}.txt", result_text)
        
        st.download_button("Pobierz ZIP", zip_buffer.getvalue(), "wyniki.zip")

# --- ZAKŁADKA 2: EDYCJA BAZY ---
with tab2:
    st.markdown("Dane są pobierane i zapisywane bezpośrednio w Twoim Arkuszu Google.")
    
    if st.button("🔄 Odśwież dane z chmury"):
        db_dict, db_df = load_data_from_sheet()
        st.session_state['cz_db'] = db_dict
        st.session_state['cz_df'] = db_df
        st.rerun()

    # Edytor tabeli
    edited_df = st.data_editor(
        st.session_state['cz_df'], 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Module": "Nazwa Modułu (z PDF)",
            "CZ": "Numery CZ (rozdziel średnikiem ;)"
        }
    )

    if st.button("💾 Zapisz zmiany w Google Sheets"):
        save_data_to_sheet(edited_df)
        # Aktualizuj lokalny słownik po zapisie
        new_db = {}
        for index, row in edited_df.iterrows():
            cz_raw = row["CZ"]
            if isinstance(cz_raw, str):
                cz_list = [x.strip() for x in cz_raw.split(';') if x.strip()]
            else:
                 cz_list = []
            new_db[row["Module"]] = cz_list
        st.session_state['cz_db'] = new_db