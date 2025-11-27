import streamlit as st
import pdfplumber
import pandas as pd
import io
import zipfile
import os
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="BN3500 Analyser", layout="wide", page_icon="⚙️")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Error secrets.toml config.")

def load_data_from_sheet():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        df = conn.read(spreadsheet=url, usecols=[0, 1], ttl=0)
        df = df.dropna()
        
        db = {}
        for index, row in df.iterrows():
            module = row[0]
            cz_raw = row[1]
            
            if isinstance(cz_raw, str):
                cz_list = [x.strip() for x in cz_raw.split(';') if x.strip()]
            else:
                cz_list = [str(cz_raw)]
                
            db[module] = cz_list
        return db, df
    except Exception as e:
        st.error(f"Error with Google Sheets connection: {e}")
        return {}, pd.DataFrame(columns=["Module", "CZ"])

def save_data_to_sheet(updated_df):
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        conn.update(spreadsheet=url, data=updated_df)
        st.cache_data.clear()
        st.success("Success!")
    except Exception as e:
        st.error(f"Error with saving data: {e}")

if 'cz_db' not in st.session_state:
    db_dict, db_df = load_data_from_sheet()
    st.session_state['cz_db'] = db_dict
    st.session_state['cz_df'] = db_df

st.title("⚙️ BN3500 Rack BOM Analyser")

tab1, tab2 = st.tabs(["Rack module analyser", "🛠️ Edit CZ numbers"])

with tab1:
    st.markdown("Upload PDF Rack Configuration Report. The system will generate TXT files for each rack and summary reports.")
    
    uploaded_files = st.file_uploader("Select PDF files", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        if st.button(f"Process {len(uploaded_files)} files"):
        
            global_unique_cz = set()
            global_missing_modules = {} # Changed to dict to store filenames
            
            current_db = st.session_state['cz_db']
            zip_buffer = io.BytesIO()
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            column_name = 'Module\nType'
            log_folder = "summary/"

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analysing: {uploaded_file.name}...")
                    
                    try:
                        name_without_ext = os.path.splitext(uploaded_file.name)[0]
                        module_types = []

                        with pdfplumber.open(uploaded_file) as pdf:
                            for page in pdf.pages:
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
                                            modbus_indexes = [i for i, x in enumerate(module_type_list) if x == modbus_name]
                                            
                                            for modbus_index in modbus_indexes:
                                                if channel_type and len(channel_type) > modbus_index:
                                                    modbus_type_str = channel_type[modbus_index]
                                                    module_type_list[modbus_index] = module_type_list[modbus_index] + ' ' + modbus_type_str
                                        module_types.extend(module_type_list)

                        module_types_unique = sorted(set(module_types))
                        file_cz_result = ''
                        
                        for module_type in module_types_unique:
                            cz_list = current_db.get(module_type)
                            
                            if cz_list:
                                for cz_item in cz_list:
                                    file_cz_result += cz_item + '\n'
                                    global_unique_cz.add(cz_item)
                            elif module_type not in ['3500 Blank Slot', '3500/15 Power Supply']:
                                if module_type not in global_missing_modules:
                                    global_missing_modules[module_type] = set()
                                global_missing_modules[module_type].add(uploaded_file.name)

                        zip_file.writestr(f"{name_without_ext}.txt", file_cz_result)

                    except Exception as e:
                        st.error(f"Błąd w pliku {uploaded_file.name}: {e}")
                    
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                summary_parts_content = ""
                for cz in sorted(global_unique_cz):
                    summary_parts_content += cz + '\n'
                zip_file.writestr(f"{log_folder}summary_log.txt", summary_parts_content)

                missing_modules_content = ""
                if global_missing_modules:
                    for missing in sorted(global_missing_modules.keys()):
                        files_list = ", ".join(sorted(global_missing_modules[missing]))
                        missing_modules_content += f"{missing} - ({files_list})\n"
                else:
                    missing_modules_content += "--- No missing modules ---\n"
                zip_file.writestr(f"{log_folder}missing_modules_log.txt", missing_modules_content)

            status_text.text("Done!")
            st.success(f"Processed {len(uploaded_files)} PDF files.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"Found {len(global_unique_cz)} matched unique CZ numbers.")
            with col2:
                if global_missing_modules:
                    st.warning(f"Not recognized {len(global_missing_modules)} module types (check log file).")
                else:
                    st.success("All modules recognized")

            st.download_button(
                label="📥 Download result (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="bn3500_rack_bom_result.zip",
                mime="application/zip"
            )

with tab2:
    st.markdown("Editing Rack Module CZ numbers")
    
    if st.button("🔄 Refresh data"):
        db_dict, db_df = load_data_from_sheet()
        st.session_state['cz_db'] = db_dict
        st.session_state['cz_df'] = db_df
        st.rerun()

    edited_df = st.data_editor(
        st.session_state['cz_df'], 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Module": st.column_config.TextColumn("Module type", width="medium"),
            "CZ": st.column_config.TextColumn("CZ number (separated by semicolon)", width="large")
        }
    )

    if st.button("💾 Save data"):
        save_data_to_sheet(edited_df)
        new_db = {}
        for index, row in edited_df.iterrows():
            module_key = row["Module"]
            cz_raw = row["CZ"]
            
            if isinstance(cz_raw, str):
                cz_list = [x.strip() for x in cz_raw.split(';') if x.strip()]
            else:
                 cz_list = []
            
            if module_key:
                new_db[module_key] = cz_list
                
        st.session_state['cz_db'] = new_db