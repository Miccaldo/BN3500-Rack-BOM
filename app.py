import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile
import os

# --- Słownik danych ---
tdi_trans_data_int = [
    'CZ-0919800-100-666 - 3500/22-01-01-00 KMPL.',
    'CZ-1119520-000-705 - 3500/22 288055-01 PRZÓD'
]
relay_standard_4 = ['CZ-0919800-100-663 - 3500/32-01-00']
tachometer_int_term = ['CZ-0919800-100-757 - 3500/50-01-00']

cz_elements = {
    '3500/22M TDI- Transient Data Int': tdi_trans_data_int,
    '3500/22M TDI-Transient Data Int': tdi_trans_data_int,
    '3500/25 Keyphasor I/O Module (Int. Term.)': ['CZ-0919800-100-704 - 3500/25-01-01 KMPL.'],
    '3500/33 16 Channel Relay Module': ['CZ-1119520-000-631 - 3500/33-01-01 KMPL.'],
    '3500/32 Standard Relay Module': relay_standard_4,
    '3500/32M Standard Relay Module': relay_standard_4,
    '3500/34 TMR Relay Module': ['CZ-0919800-100-706 - 3500/34-01-00 KMPL.'],
    '3500/40M Proximitor I/O (Int. Term.)': ['CZ-0919800-100-707 - 3500/40-01-00 KMPL.'],
    '3500/42M Prox/Velom I/O (Int. Term.)': ['CZ-0919800-100-709 - 3500/42-09-00'],
    '3500/42M Prox/Seismic I/O Module (Int. Term.)': ['CZ-0919800-100-664 - 3500/42-01-00'],
    '3500/42M Prox/Seismic I/O Module (Ext. Term.)': ['CZ-0919800-100-708 - 3500/42-02-00'],
    '3500/50M Tachometer I/O (Int. Term.)': tachometer_int_term,
    '3500/50 Tachometer I/O (Int. Term.)': tachometer_int_term,
    '3500/53 Overspeed Protection I/O (Int. Term.)': ['CZ-0919800-100-710 - 3500/53-03-00 KMPL.'],
    '3500/60 RTD/TC Temp I/O (Int. Term.)': [
        'CZ-0919800-100-705 - 3500/60-01-00 KMPL.',
        'CZ-0919800-100-765 - 163179-01 PRZÓD',
        'CZ-0919800-100-766 - 133843-01 TYŁ'
    ],
    '3500/60 Isolated TC Temp I/O (Ext. Term.)': ['CZ-0919800-100-714 - 3500/60-04-00'],
    '3500/62 PV Isolated 4-20 mA I/O (Int. Term.)': ['CZ-1119520-000-689 - 136294-01'],
    '3500/65 16 Channel Temperature I/O (Int. Term.)': ['CZ-1119520-000-633 - 3500/65-01-00'],
    '3500/70M Prox/Velom I/O (Int. Term.)': ['CZ-0919800-100-715 - 3500/70-MM-00 (opis z SAP)'],
    '3500/72M Prox/Velom I/O (Int. Term.)': ['CZ-0919800-100-716 - 3500/72-01-00'],
    '3500/77M Cylinder Pressure I/O (Int. Term.)': ['CZ-0919800-100-717 - 3500/77-03-00'],
    '3500/92 Communication Gateway RS-485': ['CZ-0919800-100-711 - 3500/92-02-01-00 - RS485'],
    '3500/92 Communication Gateway Ethernet': ['CZ-0919800-100-718 - 3500/92-04-01-00 - ETH/RS485']
}

# --- Konfiguracja Strony ---
st.set_page_config(page_title="BN3500 Converter", layout="wide")

st.title("📄 Konwerter BN3500 Rack BOM")
st.markdown("Wrzuć pliki PDF, a system wygeneruje listę części (CZ).")

# --- Upload Plików ---
uploaded_files = st.file_uploader("Wybierz pliki PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button(f"Przetwórz {len(uploaded_files)} plików"):
        
        # Przygotowanie bufora na ZIP w pamięci RAM
        zip_buffer = io.BytesIO()
        
        # Pasek postępu
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        processed_count = 0
        logs = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Przetwarzanie: {uploaded_file.name}...")
                
                try:
                    # Pobierz nazwę pliku bez rozszerzenia
                    name_without_ext = os.path.splitext(uploaded_file.name)[0]
                    module_types = []
                    column_name = 'Module\nType'

                    # Czytanie PDF z pamięci
                    with pdfplumber.open(uploaded_file) as pdf:
                        for i, page in enumerate(pdf.pages):
                            tables = page.extract_tables()
                            for table in tables:
                                if not table: continue
                                df = pd.DataFrame(table[1:], columns=table[0])
                                channel_type = None

                                if 'Channel Type' in df.columns:
                                    channel_type = df['Channel Type'].dropna().str.replace('\n', ' ', regex=True).tolist()

                                if column_name in df.columns:
                                    module_type_list = df[column_name].dropna().str.replace('\n', ' ', regex=True).tolist()
                                    
                                    modbus_name = '3500/92 Communication Gateway'
                                    if modbus_name in module_type_list:
                                        modbus_indexes = [idx for idx, x in enumerate(module_type_list) if x == modbus_name]
                                        for modbus_index in modbus_indexes:
                                            if channel_type and len(channel_type) > modbus_index:
                                                modbus_type = channel_type[modbus_index]
                                                module_type_list[modbus_index] = module_type_list[modbus_index] + ' ' + modbus_type
                                    
                                    module_types.append(module_type_list)

                    # Generowanie wyniku tekstowego
                    module_types_unique = sorted(set([item for sublist in module_types for item in sublist]))
                    cz_result = ''
                    
                    for module_type in module_types_unique:
                        cz = cz_elements.get(module_type)
                        if cz:
                            for cz_to_write in cz:
                                cz_result += cz_to_write + '\n'
                        elif module_type not in ['3500 Blank Slot', '3500/15 Power Supply']:
                             logs.append(f"[{uploaded_file.name}] Nie znaleziono: {module_type}")

                    # Dodaj plik txt do archiwum ZIP
                    zip_file.writestr(f"{name_without_ext}.txt", cz_result)
                    processed_count += 1

                except Exception as e:
                    st.error(f"Błąd przy pliku {uploaded_file.name}: {e}")
                
                # Aktualizacja paska
                progress_bar.progress((idx + 1) / len(uploaded_files))

        status_text.text("Gotowe!")
        st.success(f"Pomyślnie przetworzono {processed_count} plików.")

        # Wyświetlanie logów (ostrzeżeń)
        if logs:
            with st.expander("Zobacz ostrzeżenia (Elementy nieznalezione)"):
                for log in logs:
                    st.write(log)

        # Przycisk pobierania
        st.download_button(
            label="📥 Pobierz wyniki (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="wyniki_bn3500.zip",
            mime="application/zip"
        )