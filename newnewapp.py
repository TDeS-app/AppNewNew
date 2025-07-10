import streamlit as st
import pandas as pd
import re
from io import BytesIO
from rapidfuzz import fuzz, process
import unicodedata

st.set_page_config(layout="wide")
st.title("📦 Lean Inventory Tracker for Shopify")

# --- Helper Functions ---
def read_csv_with_fallback(uploaded_file):
    content = uploaded_file.read()
    for enc in ['utf-8-sig', 'ISO-8859-1', 'windows-1252']:
        try:
            return pd.read_csv(BytesIO(content), encoding=enc)
        except Exception:
            continue
    st.warning(f"❗ Could not read {uploaded_file.name} with common encodings.")
    return None

def contains_special_characters(text):
    return bool(re.search(r'[^\w\s\-]', str(text)))

def summarize_dataframe(df, name):
    st.subheader(f"Summary: {name}")
    st.write(f"🧾 Rows: {len(df)} | Columns: {len(df.columns)}")
    st.write(df.head())

def find_titles_with_special_chars(df, column):
    if column not in df.columns:
        return []
    return [title for title in df[column].dropna().unique() if contains_special_characters(title)]

def fuzzy_match_titles(selected_titles, inventory_df, threshold=95):
    matched_rows = []
    unmatched_titles = []
    conflict_choices = {}

    inventory_titles = inventory_df['Title'].astype(str).tolist()

    for title in selected_titles:
        matches = process.extract(title, inventory_titles, scorer=fuzz.ratio, score_cutoff=threshold)
        if not matches:
            unmatched_titles.append(title)
            continue
        elif len(matches) == 1:
            match_title = matches[0][0]
            match_rows = inventory_df[inventory_df['Title'] == match_title]
            matched_rows.append(match_rows)
        else:
            conflict_choices[title] = [match[0] for match in matches]

    return matched_rows, unmatched_titles, conflict_choices

def resolve_conflicts(conflict_choices, inventory_df):
    selected_rows = []
    for title, options in conflict_choices.items():
        choice = st.selectbox(f"Multiple matches found for '{title}'. Choose one or skip:", options + ["Skip"], key=title)
        if choice != "Skip":
            selected_rows.append(inventory_df[inventory_df['Title'] == choice])
    return selected_rows

def match_handles(product_df, inventory_df):
    return product_df[product_df['Handle'].isin(inventory_df['Handle'])]

# --- File Upload Section ---
st.sidebar.header("Step 1: Upload Files")
product_files = st.sidebar.file_uploader("Product file(s)", type="csv", accept_multiple_files=True)
inventory_files = st.sidebar.file_uploader("Inventory file(s)", type="csv", accept_multiple_files=True)
selected_file = st.sidebar.file_uploader("Selected products file", type="csv")

if product_files and inventory_files and selected_file:
    # Read and merge
    product_dfs = [read_csv_with_fallback(f) for f in product_files if f is not None]
    inventory_dfs = [read_csv_with_fallback(f) for f in inventory_files if f is not None]
    selected_df = read_csv_with_fallback(selected_file)

    if any(df is None for df in product_dfs + inventory_dfs) or selected_df is None:
        st.error("❌ Error reading files. Please check formatting.")
    else:
        product_df = pd.concat(product_dfs, ignore_index=True) if len(product_dfs) > 1 else product_dfs[0]
        inventory_df = pd.concat(inventory_dfs, ignore_index=True) if len(inventory_dfs) > 1 else inventory_dfs[0]

        special_titles = []
        special_titles += find_titles_with_special_chars(product_df, 'Title')
        special_titles += find_titles_with_special_chars(inventory_df, 'Title')
        if special_titles:
            st.warning("⚠️ Special characters found in Titles:")
            st.write(special_titles)
        else:
            st.success("✅ No special characters found in titles.")

        summarize_dataframe(product_df, "Product File")
        summarize_dataframe(inventory_df, "Inventory File")
        summarize_dataframe(selected_df, "Selected Products")

        if st.button("Proceed with Matching"):
            # Step 2: Filter Inventory based on Selected Titles
            selected_titles = selected_df['Title'].dropna().unique().tolist()
            matched, unmatched, conflicts = fuzzy_match_titles(selected_titles, inventory_df)
            conflict_rows = resolve_conflicts(conflicts, inventory_df)

            filtered_inventory = pd.concat(matched + conflict_rows, ignore_index=True)
            filtered_inventory.drop_duplicates(inplace=True)

            st.success("✅ Inventory filtering complete.")
            summarize_dataframe(filtered_inventory, "Filtered Inventory")

            # Step 3: Filter Product file based on matched handles
            if 'Handle' in product_df.columns and 'Handle' in filtered_inventory.columns:
                filtered_product = match_handles(product_df, filtered_inventory)
                filtered_product.drop_duplicates(inplace=True)
                st.success("✅ Filtered product file created.")
                summarize_dataframe(filtered_product, "Filtered Products")

                st.download_button("📥 Download Filtered Inventory CSV", data=filtered_inventory.to_csv(index=False).encode('utf-8'), file_name="filtered_inventory.csv", mime="text/csv")
                st.download_button("📥 Download Filtered Product CSV", data=filtered_product.to_csv(index=False).encode('utf-8'), file_name="filtered_product.csv", mime="text/csv")
            else:
                st.warning("⚠️ Handle column missing in one of the datasets. Skipping product filtering.")
else:
    st.info("📂 Please upload all required files to begin.")
